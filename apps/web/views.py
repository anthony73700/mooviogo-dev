from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.files.storage import default_storage
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.encoding import force_bytes
from django.utils import timezone
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.text import slugify
from django.views.i18n import set_language as django_set_language
from django.views.decorators.http import require_POST
from xml.sax.saxutils import escape as xml_escape

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from datetime import date, datetime, timedelta
from uuid import uuid4

from apps.bookings.models import Booking, PartnerAgendaEntry
from apps.chats.models import Chat
from apps.chats.models import ChatParticipant
from apps.ads.models import SponsoredEvent
from apps.authentication.phone_verification import (
    clear_phone_otp_backoff,
    consume_phone_verification_token,
    create_phone_otp,
    get_otp_alerts_last_24h,
    get_phone_otp_block_remaining,
    increment_otp_alert_metric,
    is_phone_format_valid,
    normalize_phone,
    verify_phone_otp,
)
from apps.notifications.tasks import send_notification_task
from apps.events.models import Event
from apps.partner_opportunities.models import PartnerOpportunity
from apps.partners.models import Partner
from apps.payments.models import Payment
from apps.reports.models import Report
from apps.reports.services import send_report_moderation_notifications
from apps.restaurants.models import RestaurantTimeSlot, RestaurantVenue, RestaurantVenuePhoto
from apps.sorties.models import Sortie, SortieParticipant
from apps.tickets.models import Ticket, TicketScanAudit
from mooviogo.observability import alert_on_threshold, emit_alert, emit_event

User = get_user_model()


def _is_professional_account(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_staff or user.is_superuser:
        return False
    if getattr(user, "is_partner", False):
        return True
    if Partner.objects.filter(owner=user).exists():
        return True
    return RestaurantVenue.objects.filter(owner=user, is_active=True).exists()


def _redirect_professional_account(request):
    if _is_professional_account(request.user):
        return redirect("/partenaire/")
    return None


def _ensure_upcoming_slots_for_venue(venue):
    """Keep demo restaurant booking slots usable by rolling them forward."""
    today = timezone.localdate()
    has_upcoming = RestaurantTimeSlot.objects.filter(venue=venue, date__gte=today).exists()
    if has_upcoming:
        return

    known_times = list(
        RestaurantTimeSlot.objects.filter(venue=venue)
        .order_by("time")
        .values_list("time", flat=True)
        .distinct()
    )
    if not known_times:
        known_times = [
            timezone.datetime(2000, 1, 1, 12, 30).time(),
            timezone.datetime(2000, 1, 1, 13, 0).time(),
            timezone.datetime(2000, 1, 1, 19, 30).time(),
            timezone.datetime(2000, 1, 1, 20, 0).time(),
            timezone.datetime(2000, 1, 1, 20, 30).time(),
            timezone.datetime(2000, 1, 1, 21, 0).time(),
        ]

    default_capacity = (
        RestaurantTimeSlot.objects.filter(venue=venue)
        .order_by("-capacity")
        .values_list("capacity", flat=True)
        .first()
    ) or 6

    for day_offset in range(1, 8):
        slot_date = today + timedelta(days=day_offset)
        for slot_time in known_times[:6]:
            RestaurantTimeSlot.objects.get_or_create(
                venue=venue,
                date=slot_date,
                time=slot_time,
                defaults={
                    "capacity": default_capacity,
                    "confirmed_count": 0,
                    "status": RestaurantTimeSlot.SlotStatus.OPEN,
                },
            )


def _rate_limit_key(prefix, request, extra=""):
    ip = request.META.get("REMOTE_ADDR", "unknown")
    user_id = request.user.id if request.user.is_authenticated else "anon"
    return f"{prefix}:{ip}:{user_id}:{extra}".lower().strip(":")


def _rate_limit_hit(key, ttl_seconds):
    if cache.add(key, 1, timeout=ttl_seconds):
        return 1
    try:
        return cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=ttl_seconds)
        return 1


def _is_rate_limited(key, limit):
    value = cache.get(key) or 0
    return int(value) >= int(limit)


def _reservation_kind_from_partner(partner):
    category = (getattr(partner, "category", "") or "").lower()
    if "night" in category:
        return PartnerAgendaEntry.ReservationKind.NIGHTLIFE
    if any(token in category for token in ["activ", "kart", "laser", "escape", "bowling", "paintball"]):
        return PartnerAgendaEntry.ReservationKind.ACTIVITY
    return PartnerAgendaEntry.ReservationKind.RESTAURANT


def _professional_section(user, partner_profile=None, owned_venues=None):
    if partner_profile is None:
        partner_profile = Partner.objects.filter(owner=user).first()
    if owned_venues is None:
        owned_venues = RestaurantVenue.objects.filter(owner=user, is_active=True)

    explicit_section = (getattr(partner_profile, "pro_section", "") or "").strip().lower()
    if explicit_section in {"restaurant", "nightlife", "activity"}:
        return explicit_section

    category = (getattr(partner_profile, "category", "") or "").lower()
    if "night" in category:
        return "nightlife"
    if any(token in category for token in ["sort", "activ", "kart", "laser", "escape", "bowling", "paintball"]):
        return "sortie"
    if "rest" in category:
        return "restaurant"

    if owned_venues.exists():
        return "restaurant"
    return "sortie"


def _professional_public_page_payload(user):
    partner_profile = Partner.objects.filter(owner=user).first()

    if partner_profile and partner_profile.slug:
        return {
            "url": f"/partenaires/public/{partner_profile.slug}/",
            "label": "Voir ma page partenaire publique",
        }

    owned_venue = RestaurantVenue.objects.filter(owner=user, is_active=True).order_by("id").first()
    if owned_venue:
        return {
            "url": f"/restaurants/{owned_venue.city_slug}/{owned_venue.slug}/?as_public=1",
            "label": "Voir ma fiche restaurant publique",
        }

    return {"url": "", "label": ""}


def _section_allowed_kinds(section):
    if section == "restaurant":
        return {PartnerAgendaEntry.ReservationKind.RESTAURANT}
    if section == "nightlife":
        return {PartnerAgendaEntry.ReservationKind.NIGHTLIFE}
    return {PartnerAgendaEntry.ReservationKind.ACTIVITY, PartnerAgendaEntry.ReservationKind.OTHER}


def _section_default_kind(section):
    if section == "restaurant":
        return PartnerAgendaEntry.ReservationKind.RESTAURANT
    if section == "nightlife":
        return PartnerAgendaEntry.ReservationKind.NIGHTLIFE
    return PartnerAgendaEntry.ReservationKind.ACTIVITY


def _ui_revision_tag():
    # Visible runtime tag used to confirm the browser is rendering the latest backend/template version.
    return timezone.localtime().strftime("LIVE %d/%m %H:%M:%S")


def _build_organizer_identity(user):
    if not user:
        return {
            "display": "Membre",
            "initials": "MB",
            "avatar_url": "",
        }

    first_name = (getattr(user, "first_name", "") or "").strip()
    last_name = (getattr(user, "last_name", "") or "").strip()
    display_name = (getattr(user, "display_name", "") or "").strip()
    username = (getattr(user, "username", "") or "").strip()
    avatar_url = (getattr(user, "avatar_url", "") or "").strip()

    if first_name:
        display = f"{first_name} {last_name[:1].upper()}." if last_name else first_name
    elif last_name:
        display = f"{last_name[:1].upper()}."
    elif display_name:
        name_tokens = [token for token in display_name.replace(".", " ").split() if token]
        if len(name_tokens) >= 2:
            display = f"{name_tokens[0].capitalize()} {name_tokens[1][:1].upper()}."
        elif len(name_tokens) == 1:
            display = name_tokens[0].capitalize()
        else:
            display = "Membre"
    else:
        # Fallback: turn usernames like "sophie_m" or "sophie-martin" into "Sophie M."
        normalized = username.replace("_", " ").replace("-", " ").replace(".", " ").strip()
        tokens = [token for token in normalized.split() if token]
        if tokens:
            first_guess = tokens[0].capitalize()
            if len(first_guess) <= 2 and any(ch.isdigit() for ch in first_guess):
                display = "Membre"
            elif len(tokens) > 1:
                display = f"{first_guess} {tokens[1][:1].upper()}."
            else:
                display = first_guess if len(first_guess) > 2 else "Membre"
        else:
            display = "Membre"

    display_tokens = [token for token in display.replace(".", "").split() if token]
    if len(display_tokens) >= 2:
        initials = f"{display_tokens[0][:1].upper()}{display_tokens[1][:1].upper()}"
    elif len(display_tokens) == 1:
        token = display_tokens[0]
        initials = (token[:2] if len(token) >= 2 else f"{token[:1]}X").upper()
    else:
        initials = "MB"

    return {
        "display": display,
        "initials": initials,
        "avatar_url": avatar_url,
    }


def _attach_sorties_organizer_identity(sorties):
    for sortie in sorties:
        identity = _build_organizer_identity(getattr(sortie, "creator", None))
        sortie.organizer_display = identity["display"]
        sortie.organizer_initials = identity["initials"]
        sortie.organizer_avatar_url = identity["avatar_url"]


def _activity_offer_two_details():
    return {
        "name": "Offre Activite 2 - Pro IA",
        "price": "79 EUR / mois HT",
        "features": [
            "Tout Starter inclus",
            "IA Marketing: posts Instagram, hashtags, descriptions et textes promotionnels",
            "IA Campagnes: relance clients absents, promotions heures creuses, campagnes automatiques",
            "Analytics avancees: frequentation, conversion, remplissage, heures rentables, clients recurrents",
            "Notifications avancees: push, SMS, WhatsApp",
            "Mise en avant partenaire sur la plateforme",
            "Support prioritaire et onboarding accelere",
            "Billetterie QR code et validation participants",
        ],
        "examples": [
            "Session karting entreprise 18h30, 12 participants, paiement confirme",
            "Pack laser game anniversaire en attente de validation",
            "Campagne automatique heure creuse activee pour mardi 15h",
        ],
    }


def _partner_demo_rows(kind):
    now = timezone.localtime()
    if kind == "events":
        return [
            {"title": "Soiree Karting Corporate", "meta": f"Marseille - {(now + timedelta(days=1)).strftime('%a %d/%m')} 18:30 - PUBLIE"},
            {"title": "Session Laser Game Etudiant", "meta": f"Aix-en-Provence - {(now + timedelta(days=2)).strftime('%a %d/%m')} 21:00 - PUBLIE"},
            {"title": "Escape Game Team Building", "meta": f"Marseille - {(now + timedelta(days=3)).strftime('%a %d/%m')} 19:15 - BROUILLON"},
            {"title": "Challenge Bowling Inter-entreprises", "meta": f"Vitrolles - {(now + timedelta(days=4)).strftime('%a %d/%m')} 20:00 - EN VALIDATION"},
            {"title": "Tournoi Karting Nocturne", "meta": f"Marseille - {(now + timedelta(days=5)).strftime('%a %d/%m')} 22:00 - COMPLET"},
        ]
    if kind == "payments":
        return [
            {"title": "pi_demo_confirm_001", "meta": f"Confirme - 189.00 EUR - Karting corporate - {(now - timedelta(days=1)).strftime('%d/%m')}"},
            {"title": "pi_demo_pending_002", "meta": f"En attente - 72.00 EUR - Laser game groupe - {now.strftime('%d/%m')}"},
            {"title": "pi_demo_confirm_003", "meta": f"Confirme - 129.00 EUR - Escape game famille - {(now + timedelta(days=1)).strftime('%d/%m')}"},
            {"title": "pi_demo_refund_004", "meta": f"Rembourse - 45.00 EUR - Annulation client - {(now + timedelta(days=2)).strftime('%d/%m')}"},
            {"title": "pi_demo_capture_005", "meta": f"Capture programmee - 210.00 EUR - EVG karting - {(now + timedelta(days=3)).strftime('%d/%m')}"},
        ]
    if kind == "requests":
        return [
            {"title": "Demande anniversaire 14 personnes", "meta": f"Marseille - EN ATTENTE - {(now + timedelta(days=1)).strftime('%a %d/%m')} 16:00"},
            {"title": "Demande EVG karting", "meta": f"Marseille - CONFIRMEE - Acompte 90 EUR recu - {(now + timedelta(days=2)).strftime('%a %d/%m')}"},
            {"title": "Demande groupe scolaire", "meta": f"Aix-en-Provence - EN REVUE - Devis 240 EUR - {(now + timedelta(days=3)).strftime('%a %d/%m')}"},
            {"title": "Demande afterwork startup", "meta": f"Marseille - EN ATTENTE CLIENT - {(now + timedelta(days=4)).strftime('%a %d/%m')} 19:30"},
            {"title": "Demande team building 22 pers.", "meta": f"Vitrolles - CONFIRMEE - Paiement total recu - {(now + timedelta(days=5)).strftime('%a %d/%m')}"},
        ]
    return []


def _normalize_dashboard_section(section):
    section_key = (section or "").strip().lower()
    if section_key == "sortie":
        return "activity"
    if section_key in {"restaurant", "nightlife", "activity"}:
        return section_key
    return "activity"


def _dashboard_section_config(section):
    configs = {
        "restaurant": {
            "label": "Restaurant",
            "headline": "Dashboard Restaurant",
            "description": "Pilotage service, tables, reservations et satisfaction client.",
            "hero_points": ["Service fluide", "Remplissage intelligent", "Equipe synchronisee"],
            "offers": [
                {
                    "key": "starter",
                    "name": "Restaurant Starter",
                    "price": "39 EUR / mois HT",
                    "tagline": "Lancer et structurer le service",
                    "features": [
                        "Fiche etablissement complete",
                        "Calendrier de services (midi/soir)",
                        "Reservations manuelles et Mooviogo",
                        "Notifications email",
                        "Journal de reservation 30 jours",
                    ],
                },
                {
                    "key": "pro",
                    "name": "Restaurant Pro",
                    "price": "79 EUR / mois HT",
                    "tagline": "Monter en conversion et productivite",
                    "features": [
                        "Tout Starter inclus",
                        "Automatisations confirmation / relance",
                        "SMS + WhatsApp + push",
                        "Statistiques service et no-show",
                        "Promotions heures creuses",
                        "API caisse / PMS",
                    ],
                },
                {
                    "key": "elite",
                    "name": "Restaurant Elite IA",
                    "price": "149 EUR / mois HT",
                    "tagline": "Operation premium multi-etablissements",
                    "features": [
                        "Tout Pro inclus",
                        "Prevision IA affluence et staffing",
                        "Segmentation clients et campagnes IA",
                        "A/B testing offres et menus",
                        "Support prioritaire + onboarding dedie",
                        "Multi-sites et gouvernance equipe",
                    ],
                },
            ],
        },
        "nightlife": {
            "label": "Nightlife",
            "headline": "Dashboard Nightlife",
            "description": "Billetterie, controle d'acces, line-up et revenus evenementiels.",
            "hero_points": ["Billetterie performante", "Entree securisee", "Nuits rentables"],
            "offers": [
                {
                    "key": "starter",
                    "name": "Nightlife Starter",
                    "price": "49 EUR / mois HT",
                    "tagline": "Publier et vendre ses premieres soirees",
                    "features": [
                        "Creation evenements illimitee",
                        "Billetterie standard",
                        "QR code de base",
                        "Suivi ventes temps reel",
                        "Notifications email",
                    ],
                },
                {
                    "key": "pro",
                    "name": "Nightlife Pro",
                    "price": "99 EUR / mois HT",
                    "tagline": "Accelerer ventes et fluidite d'entree",
                    "features": [
                        "Tout Starter inclus",
                        "QR scan rapide multi-terminaux",
                        "Listes VIP et pre-ventes",
                        "Relances automatiques paniers",
                        "Segmentation audience",
                        "Rapports revenu par event",
                    ],
                },
                {
                    "key": "elite",
                    "name": "Nightlife Elite IA",
                    "price": "179 EUR / mois HT",
                    "tagline": "Stack complet pour clubs et festivals",
                    "features": [
                        "Tout Pro inclus",
                        "Pricing dynamique par IA",
                        "Detection fraude avanc ee",
                        "Attribution marketing omnicanale",
                        "CRM promoters et commissions",
                        "Customer success dedie",
                    ],
                },
            ],
        },
        "activity": {
            "label": "Activite",
            "headline": "Dashboard Activite",
            "description": "Reservations, sessions, groupes et performance commerciale en continu.",
            "hero_points": ["Planning net", "Conversion groupe", "Operations precises"],
            "offers": [
                {
                    "key": "starter",
                    "name": "Activite Starter",
                    "price": "35 EUR / mois HT",
                    "tagline": "Demarrer avec un pilotage simple",
                    "features": [
                        "Fiche activite et disponibilites",
                        "Reservations directes + Mooviogo",
                        "Agenda operationnel",
                        "Notifications email",
                        "Rapport hebdomadaire",
                    ],
                },
                {
                    "key": "pro",
                    "name": "Activite 2 - Pro IA",
                    "price": "79 EUR / mois HT",
                    "tagline": "Automatiser marketing et operations",
                    "features": [
                        "Tout Starter inclus",
                        "IA Marketing (posts, descriptions, hashtags)",
                        "IA Campagnes (relances et heures creuses)",
                        "Analytics avancees (conversion, remplissage)",
                        "Notifications push/SMS/WhatsApp",
                        "Billetterie QR code",
                    ],
                },
                {
                    "key": "elite",
                    "name": "Activite Elite",
                    "price": "139 EUR / mois HT",
                    "tagline": "Scale multi-sites et optimisation predictive",
                    "features": [
                        "Tout Pro inclus",
                        "Forecast IA demande et capacite",
                        "Tarification intelligente par session",
                        "Scenarios de remplissage auto",
                        "Multi-sites et roles avances",
                        "Support prioritaire 7j/7",
                    ],
                },
            ],
        },
    }
    return configs.get(section, configs["activity"])


def _resolve_active_offer_key(partner_profile, section):
    tier_to_offer = {
        "low": "starter",
        "mid": "pro",
        "high": "elite",
    }
    explicit_tier = (getattr(partner_profile, "pro_offer_tier", "") or "").strip().lower()
    if explicit_tier in tier_to_offer:
        return tier_to_offer[explicit_tier]

    text = ""
    if partner_profile:
        text = " ".join([
            getattr(partner_profile, "category", "") or "",
            getattr(partner_profile, "short_description", "") or "",
            getattr(partner_profile, "description", "") or "",
        ]).lower()

    if any(token in text for token in ["elite", "premium", "enterprise"]):
        return "elite"
    if any(token in text for token in ["pro", "activite 2", "business"]):
        return "pro"
    if any(token in text for token in ["starter", "basic", "essentiel"]):
        return "starter"

    defaults = {
        "restaurant": "starter",
        "nightlife": "starter",
        "activity": "pro",
    }
    return defaults.get(section, "pro")


def _offer_rank_for_user(user):
    partner_profile = Partner.objects.filter(owner=user).first()
    rank = {
        "low": 0,
        "mid": 1,
        "high": 2,
    }
    tier = (getattr(partner_profile, "pro_offer_tier", "mid") or "mid").lower()
    return rank.get(tier, 1)


def _require_offer_tier(request, minimum_tier, feature_label, fallback_url="/partner/settings/"):
    required_rank = {"low": 0, "mid": 1, "high": 2}.get(minimum_tier, 0)
    current_rank = _offer_rank_for_user(request.user)
    if current_rank >= required_rank:
        return None

    tier_label = {
        "low": "offre basse",
        "mid": "offre moyenne",
        "high": "offre haute",
    }.get(minimum_tier, minimum_tier)
    messages.error(request, f"Option non disponible: {feature_label} requiert au minimum {tier_label}.")
    return redirect(fallback_url)


def _build_offers_with_lock(config, active_offer_key):
    offers = config["offers"]
    order = [offer["key"] for offer in offers]
    active_index = order.index(active_offer_key) if active_offer_key in order else 0

    cards = []
    for index, offer in enumerate(offers):
        is_active = index == active_index
        is_locked = index > active_index
        cards.append({
            **offer,
            "is_active": is_active,
            "is_locked": is_locked,
            "state_label": "Active" if is_active else ("Bloquee" if is_locked else "Incluse"),
        })
    return cards


def _dashboard_kpis_for_section(section, user, partner_profile):
    if section == "restaurant":
        venue_count = RestaurantVenue.objects.filter(owner=user, is_active=True).count() or 1
        pending = Booking.objects.filter(booking_type=Booking.BookingType.RESTAURANT, status=Booking.Status.PENDING).count() or 6
        confirmed = Booking.objects.filter(booking_type=Booking.BookingType.RESTAURANT, status=Booking.Status.CONFIRMED).count() or 28
        return [
            {"label": "Tables actives", "value": str(venue_count), "meta": "etablissement(s) en service"},
            {"label": "Reservations", "value": str(pending), "meta": "en attente de validation"},
            {"label": "Confirmees", "value": str(confirmed), "meta": "sur les 7 derniers jours"},
            {"label": "No-show", "value": "3.1%", "meta": "controle via relance auto"},
        ]

    if section == "nightlife":
        tickets = Booking.objects.filter(booking_type=Booking.BookingType.ACTIVITY, status=Booking.Status.CONFIRMED).count() or 412
        pending_events = Event.objects.filter(is_partner_event=True, status=Event.Status.DRAFT).count() or 4
        return [
            {"label": "Billets vendus", "value": str(tickets), "meta": "periode glissante 30 jours"},
            {"label": "Events a publier", "value": str(pending_events), "meta": "drafts prets a lancer"},
            {"label": "Scan entree", "value": "98.4%", "meta": "tickets valides sans incident"},
            {"label": "Panier moyen", "value": "34 EUR", "meta": "hors extras"},
        ]

    activity_entries = PartnerAgendaEntry.objects.filter(
        owner=user,
        reservation_kind__in={
            PartnerAgendaEntry.ReservationKind.ACTIVITY,
            PartnerAgendaEntry.ReservationKind.OTHER,
        },
    )
    pending = activity_entries.filter(status=PartnerAgendaEntry.Status.PENDING).count() or 5
    confirmed = activity_entries.filter(status=PartnerAgendaEntry.Status.CONFIRMED).count() or 18
    return [
        {"label": "Sessions", "value": str(activity_entries.count() or 24), "meta": "planifiees cette semaine"},
        {"label": "Demandes", "value": str(pending), "meta": "en attente"},
        {"label": "Confirmees", "value": str(confirmed), "meta": "validations effectuees"},
        {"label": "Conversion", "value": "31%", "meta": "demandes vers confirmation"},
    ]


def _dashboard_live_examples(section, now):
    if section == "restaurant":
        return [
            f"{(now + timedelta(days=1)).strftime('%a %d/%m')} · Reservation table 6 pers. - 20:15 · CONFIRMEE",
            f"{(now + timedelta(days=2)).strftime('%a %d/%m')} · Relance no-show envoyee a 3 clients",
            f"{(now + timedelta(days=3)).strftime('%a %d/%m')} · Encaissement service soir: 1 240 EUR",
        ]
    if section == "nightlife":
        return [
            f"{(now + timedelta(days=1)).strftime('%a %d/%m')} · Event rooftop 350 billets publie",
            f"{(now + timedelta(days=2)).strftime('%a %d/%m')} · Scan QR entree: file d'attente < 4 min",
            f"{(now + timedelta(days=3)).strftime('%a %d/%m')} · Campagne aftermovie envoyee aux participants",
        ]
    return [
        f"{(now + timedelta(days=1)).strftime('%a %d/%m')} · Demande recue: Anniversaire 10 pers. - EN ATTENTE",
        f"{(now + timedelta(days=2)).strftime('%a %d/%m')} · Reservation confirmee: Laser game 6 pers. - 20:30",
        f"{(now + timedelta(days=3)).strftime('%a %d/%m')} · Paiement confirme: 149.00 EUR - Stripe",
    ]


@require_POST
def set_language_and_preference(request):
    response = django_set_language(request)
    if not request.user.is_authenticated:
        return response

    active_lang = (request.POST.get("language") or "").lower().split("-")[0]
    supported_langs = {code for code, _ in settings.LANGUAGES}
    if active_lang in supported_langs and request.user.preferred_language != active_lang:
        User.objects.filter(pk=request.user.pk).update(preferred_language=active_lang)
        request.user.preferred_language = active_lang

    return response


# ──────────────────────────────────────────────────────────────────────────────
# Home
# ──────────────────────────────────────────────────────────────────────────────

def home(request):
    professional_redirect = _redirect_professional_account(request)
    if professional_redirect:
        return professional_redirect

    sorties = (
        Sortie.objects.filter(status=Sortie.Status.OPEN)
        .select_related("creator")
        .annotate(participant_count=Count("participants"))
        .order_by("-created_at")
    )
    restaurants = RestaurantVenue.objects.filter(is_active=True).order_by("-updated_at")
    partners = Partner.objects.filter(status=Partner.Status.ACTIVE, is_verified=True).order_by("name")
    activities_sorties = (
        Sortie.objects.filter(status=Sortie.Status.OPEN, type=Sortie.Type.PARTENAIRE)
        .select_related("creator", "partner")
        .annotate(participant_count=Count("participants"))
        .order_by("-created_at")
    )

    sorties_items = list(sorties[:10])
    _attach_sorties_organizer_identity(sorties_items)
    activities_items = list(activities_sorties[:10])
    _attach_sorties_organizer_identity(activities_items)

    response = render(request, "web/home.html", {
        "sorties": sorties_items,
        "activities_sorties": activities_items,
        "events": Event.objects.filter(status=Event.Status.PUBLISHED).order_by("starts_at")[:10],
        "restaurants": restaurants[:10],
        "partners": partners[:10],
        "total_count": sorties.count(),
    })
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


def explore(request):
    professional_redirect = _redirect_professional_account(request)
    if professional_redirect:
        return professional_redirect

    q = request.GET.get("q", "").strip()
    city = request.GET.get("city", "").strip()

    sorties = Sortie.objects.filter(status=Sortie.Status.OPEN).order_by("-created_at")
    events = Event.objects.filter(status=Event.Status.PUBLISHED).order_by("starts_at")
    partners = Partner.objects.filter(status=Partner.Status.ACTIVE, is_verified=True).order_by("name")

    if city:
        sorties = sorties.filter(city__icontains=city)
        events = events.filter(city__icontains=city)
        partners = partners.filter(city__icontains=city)

    if q:
        sorties = sorties.filter(Q(title__icontains=q) | Q(description__icontains=q) | Q(location__icontains=q))
        events = events.filter(Q(title__icontains=q) | Q(description__icontains=q))
        partners = partners.filter(Q(name__icontains=q) | Q(description__icontains=q) | Q(category__icontains=q))

    return render(request, "web/platform/hub.html", {
        "page_title": "Explore",
        "page_kicker": "Decouvrir",
        "page_description": "Trouve des sorties entre membres, activites partenaires et evenements nightlife pres de chez toi.",
        "sorties": sorties[:12],
        "events": events[:12],
        "partners": partners[:12],
        "city": city,
        "search_query": q,
    })

def nightlife(request):
    professional_redirect = _redirect_professional_account(request)
    if professional_redirect:
        return professional_redirect

    city = request.GET.get("city", "").strip()
    events = Event.objects.filter(status=Event.Status.PUBLISHED, is_partner_event=True).order_by("starts_at")
    if city:
        events = events.filter(city__icontains=city)
    return render(request, "web/platform/hub.html", {
        "page_title": "Nightlife",
        "page_kicker": "Monde de la nuit",
        "page_description": "Discotheques, bars, rooftops, concerts et soirees etudiantes.",
        "events": events[:24],
        "sorties": Sortie.objects.none(),
        "partners": Partner.objects.none(),
        "city": city,
    })


def activities(request):
    professional_redirect = _redirect_professional_account(request)
    if professional_redirect:
        return professional_redirect

    q = request.GET.get("q", "").strip()
    city = request.GET.get("city", "").strip()
    free = request.GET.get("free", "")

    qs = (
        Sortie.objects.all()
        .select_related("creator", "partner")
        .annotate(participant_count=Count("participants"))
        .filter(type=Sortie.Type.PARTENAIRE)
        .order_by("-created_at")
    )

    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if city:
        qs = qs.filter(city__icontains=city)
    if free == "1":
        qs = qs.filter(is_free=True)
    elif free == "0":
        qs = qs.filter(is_free=False)

    hero_sortie = qs.exclude(cover_image_url="").first() or qs.first()

    total_count = qs.count()
    member_count = 0
    partner_count = total_count

    partner_ids_in_activities = list(
        qs.exclude(partner__isnull=True)
        .values_list("partner_id", flat=True)
        .distinct()
    )
    activity_partners = list(
        Partner.objects.filter(
            id__in=partner_ids_in_activities,
            status=Partner.Status.ACTIVE,
            is_verified=True,
            pro_section=Partner.ProSection.ACTIVITY,
        ).order_by("name")
    )
    if not activity_partners:
        activity_partners = list(
            Partner.objects.filter(
                status=Partner.Status.ACTIVE,
                is_verified=True,
                pro_section=Partner.ProSection.ACTIVITY,
            ).order_by("name")
        )

    activity_partners_carousel = []
    if activity_partners:
        target_cards = 50
        repeat_count = (target_cards + len(activity_partners) - 1) // len(activity_partners)
        activity_partners_carousel = (activity_partners * repeat_count)[:target_cards]

    member_sorties = []
    partner_sorties = []
    is_all_types = False
    partner_choices = Partner.objects.filter(
        status=Partner.Status.ACTIVE,
        is_verified=True,
    ).order_by("name")

    paginator = Paginator(qs, 18)
    page_obj = paginator.get_page(request.GET.get("page"))
    _attach_sorties_organizer_identity(page_obj.object_list)
    sorties = page_obj
    is_paginated = paginator.num_pages > 1

    return render(request, "web/sorties/list.html", {
        "sorties": sorties,
        "member_sorties": member_sorties,
        "partner_sorties": partner_sorties,
        "is_all_types": is_all_types,
        "hero_sortie": hero_sortie,
        "page_obj": page_obj,
        "is_paginated": is_paginated,
        "total_count": total_count,
        "member_count": member_count,
        "partner_count": partner_count,
        "page_title": "Activités",
        "page_kicker": "Activités partenaires",
        "page_heading": "Les activités à rejoindre ce soir.",
        "page_description": "Une lecture plus simple et plus éditoriale des activités partenaires, pour comprendre l’ambiance et décider plus vite.",
        "is_activities_page": True,
        "is_partner_only_page": True,
        "activity_partners": activity_partners,
        "activity_partners_carousel": activity_partners_carousel,
        "partner_choices": partner_choices,
        "list_base_path": "/activities/",
        "sortie_detail_base_path": "/sorties/",
        "create_sortie_base_path": "/sorties/creer/",
        "ui_revision": _ui_revision_tag(),
    })


def pricing_page(request):
    return render(request, "web/platform/simple_page.html", {
        "title": "Pricing",
        "subtitle": "Abonnements et frais plateforme",
        "description": "Consulte les formules utilisateurs, partenaires et les frais applicables selon les activites.",
        "actions": [
            {"href": "/devenir-partenaire/", "label": "Devenir partenaire"},
            {"href": "/partner/payments/", "label": "Voir les paiements"},
        ],
    })


def payment_success_page(request):
    return render(request, "web/platform/simple_page.html", {
        "title": "Paiement confirme",
        "subtitle": "Transaction reussie",
        "description": "Ton paiement a ete confirme. Tu peux retrouver le ticket dans ton espace utilisateur.",
        "actions": [
            {"href": "/my-tickets/", "label": "Mes tickets"},
            {"href": "/explore/", "label": "Continuer"},
        ],
    })


def payment_cancel_page(request):
    return render(request, "web/platform/simple_page.html", {
        "title": "Paiement annule",
        "subtitle": "Aucune transaction finalisee",
        "description": "Le paiement a ete annule. Tu peux relancer la reservation quand tu veux.",
        "actions": [
            {"href": "/my-tickets/", "label": "Verifier mes reservations"},
            {"href": "/explore/", "label": "Retour a l'exploration"},
        ],
    })


def search_page(request):
    professional_redirect = _redirect_professional_account(request)
    if professional_redirect:
        return professional_redirect

    q = request.GET.get("q", "").strip()

    sorties = Sortie.objects.none()
    events = Event.objects.none()
    partners = Partner.objects.none()
    restaurants = RestaurantVenue.objects.none()

    if q:
        sorties = Sortie.objects.filter(
            Q(title__icontains=q) | Q(description__icontains=q) | Q(city__icontains=q)
        ).order_by("-created_at")[:10]
        events = Event.objects.filter(
            Q(title__icontains=q) | Q(description__icontains=q) | Q(city__icontains=q)
        ).order_by("starts_at")[:10]
        partners = Partner.objects.filter(
            Q(name__icontains=q) | Q(description__icontains=q) | Q(city__icontains=q)
        ).order_by("name")[:10]
        restaurants = RestaurantVenue.objects.filter(
            Q(name__icontains=q) | Q(description__icontains=q) | Q(city__icontains=q)
        ).order_by("name")[:10]

    return render(request, "web/platform/search.html", {
        "query": q,
        "sorties": sorties,
        "events": events,
        "partners": partners,
        "restaurants": restaurants,
    })


# ──────────────────────────────────────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        if _is_professional_account(request.user):
            return redirect("/partenaire/")
        return redirect("/")
    error = None
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is None:
            # Try by email
            try:
                u = User.objects.get(email=username)
                user = authenticate(request, username=u.username, password=password)
            except User.DoesNotExist:
                pass
        if user:
            login(request, user)
            if _is_professional_account(user):
                return redirect("/partenaire/")
            return redirect(request.GET.get("next") or "/")
        error = "Identifiants incorrects."
    return render(request, "web/auth/login.html", {"error": error})


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("/")
    error = None
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        phone_raw = request.POST.get("phone", "").strip()
        otp_code = request.POST.get("otp_code", "").strip()
        birth_date_raw = request.POST.get("birth_date", "").strip()
        password = request.POST.get("password", "")
        password2 = request.POST.get("password2", "")
        turnstile_token = request.POST.get("cf-turnstile-response", "").strip()
        phone = normalize_phone(phone_raw)

        # Anti-bot check (no-op when TURNSTILE_SECRET_KEY is empty)
        from apps.web.turnstile import verify_turnstile

        if not verify_turnstile(turnstile_token, remote_ip=request.META.get("REMOTE_ADDR", "")):
            error = "Verification anti-bot echouee. Reessaie."
            return render(request, "web/auth/signup.html", {"error": error})

        if password != password2:
            error = "Les mots de passe ne correspondent pas."
        elif User.objects.filter(username=username).exists():
            error = "Ce nom d'utilisateur est déjà pris."
        elif User.objects.filter(email=email).exists():
            error = "Cet email est déjà utilisé."
        elif not phone:
            error = "Ton numero de telephone est obligatoire."
        elif not is_phone_format_valid(phone):
            error = "Numero de telephone invalide (format international attendu)."
        elif User.objects.filter(phone=phone).exists():
            error = "Ce numero de telephone est deja utilise."
        elif not otp_code:
            error = "Le code OTP est obligatoire."
        elif not birth_date_raw:
            error = "Ta date de naissance est obligatoire."
        else:
            try:
                birth_date = date.fromisoformat(birth_date_raw)
            except ValueError:
                birth_date = None
                error = "Format de date de naissance invalide."

        if not error and birth_date:
            age = date.today().year - birth_date.year - ((date.today().month, date.today().day) < (birth_date.month, birth_date.day))
            if age < 18:
                error = "Tu dois avoir au moins 18 ans pour t'inscrire."

        if not error:
            if len(password) < 8:
                error = "Le mot de passe doit contenir au moins 8 caractères."
            else:
                blocked_for = get_phone_otp_block_remaining(phone)
                if blocked_for > 0:
                    increment_otp_alert_metric()
                    emit_alert(
                        "auth.web.signup_verify_otp.blocked",
                        request=request,
                        severity="warning",
                        phone=phone,
                        blocked_seconds=blocked_for,
                    )
                    error = "Trop de codes invalides. Reessaie plus tard."
                    return render(request, "web/auth/signup.html", {"error": error})

                verification_token = verify_phone_otp(phone, otp_code)
                if not verification_token or not consume_phone_verification_token(phone, verification_token):
                    blocked_after = get_phone_otp_block_remaining(phone)
                    if blocked_after > 0:
                        emit_alert(
                            "auth.web.signup_verify_otp.backoff",
                            request=request,
                            severity="warning",
                            phone=phone,
                            blocked_seconds=blocked_after,
                        )
                        error = "Trop de codes invalides. Reessaie plus tard."
                        return render(request, "web/auth/signup.html", {"error": error})
                    error = "Code OTP invalide ou expire."
                    return render(request, "web/auth/signup.html", {"error": error})

                user = User.objects.create_user(
                    username=username,
                    email=email,
                    phone=phone,
                    phone_verified_at=timezone.now(),
                    birth_date=birth_date,
                    password=password,
                )
                login(request, user)
                return redirect(request.GET.get("next") or "/")
    return render(request, "web/auth/signup.html", {"error": error})


@require_POST
def signup_request_otp_view(request):
    phone = normalize_phone((request.POST.get("phone") or "").strip())
    ip_key = _rate_limit_key("signup-request-otp", request)
    phone_key = _rate_limit_key("signup-request-otp", request, phone)
    if _is_rate_limited(ip_key, 12) or (phone and _is_rate_limited(phone_key, 5)):
        increment_otp_alert_metric()
        emit_alert(
            "auth.signup_request_otp.rate_limited",
            request=request,
            severity="warning",
            phone=phone,
        )
        return JsonResponse({"detail": "Trop de demandes OTP. Reessaie plus tard."}, status=429)

    if not phone:
        return JsonResponse({"detail": "Numero de telephone requis."}, status=400)
    if not is_phone_format_valid(phone):
        return JsonResponse({"detail": "Numero de telephone invalide."}, status=400)
    if User.objects.filter(phone=phone).exists():
        return JsonResponse({"detail": "Ce numero de telephone est deja utilise."}, status=400)

    blocked_for = get_phone_otp_block_remaining(phone)
    if blocked_for > 0:
        increment_otp_alert_metric()
        emit_alert(
            "auth.signup_request_otp.blocked",
            request=request,
            severity="warning",
            phone=phone,
            blocked_seconds=blocked_for,
        )
        return JsonResponse({"detail": "OTP temporairement bloque sur ce numero.", "blocked_seconds": blocked_for}, status=429)

    _rate_limit_hit(ip_key, ttl_seconds=3600)
    _rate_limit_hit(phone_key, ttl_seconds=3600)
    clear_phone_otp_backoff(phone)

    otp_code = create_phone_otp(phone)
    message = f"Ton code Mooviogo: {otp_code}. Code valable 10 minutes."
    try:
        try:
            send_notification_task.delay(channel="sms", to=phone, message=message, subject="Mooviogo OTP")
        except Exception:
            send_notification_task.run(channel="sms", to=phone, message=message, subject="Mooviogo OTP")
    except Exception:
        # In dev environments without SMS provider credentials, keep flow testable.
        pass

    payload = {"detail": "Code OTP envoye."}
    if settings.DEBUG:
        payload["debug_code"] = otp_code
    return JsonResponse(payload, status=200)


def forgot_password_view(request):
    reset_link = ""
    submitted = False

    if request.method == "POST":
        email_raw = (request.POST.get("email") or "").strip().lower()
        turnstile_token = (request.POST.get("cf-turnstile-response") or "").strip()

        # Anti-bot check (no-op when TURNSTILE_SECRET_KEY is empty)
        from apps.web.turnstile import verify_turnstile

        if not verify_turnstile(turnstile_token, remote_ip=request.META.get("REMOTE_ADDR", "")):
            messages.error(request, "Verification anti-bot echouee. Reessaie.")
            return render(
                request,
                "web/auth/reset_password_request.html",
                {"submitted": True, "reset_link": ""},
                status=400,
            )

        ip_key = _rate_limit_key("forgot-password", request)
        email_key = _rate_limit_key("forgot-password", request, email_raw)
        if _is_rate_limited(ip_key, 20) or _is_rate_limited(email_key, 5):
            emit_alert(
                "auth.forgot_password.rate_limited",
                request=request,
                severity="warning",
                email=email_raw,
            )
            messages.error(request, "Trop de tentatives. Reessaie dans quelques minutes.")
            return render(
                request,
                "web/auth/reset_password_request.html",
                {
                    "submitted": True,
                    "reset_link": "",
                },
                status=429,
            )

        _rate_limit_hit(ip_key, ttl_seconds=3600)
        if email_raw:
            _rate_limit_hit(email_key, ttl_seconds=3600)

        submitted = True
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            users = User.objects.filter(email__iexact=email, is_active=True)

            # In this environment we expose a reset URL directly for fast QA.
            user = users.first()
            if user:
                uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                reset_link = f"/reset-password/{uidb64}/{token}/"
                absolute_reset_link = request.build_absolute_uri(reset_link)
                try:
                    send_mail(
                        subject="Reinitialisation de votre mot de passe Mooviogo",
                        message=(
                            "Bonjour,\n\n"
                            "Vous avez demande la reinitialisation de votre mot de passe. "
                            f"Utilisez ce lien: {absolute_reset_link}\n\n"
                            "Si vous n'etes pas a l'origine de cette demande, ignorez ce message."
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[user.email],
                        fail_silently=False,
                    )
                    emit_event("auth.password_reset_email_sent", request=request, email=email)
                except Exception as exc:
                    emit_alert(
                        "auth.password_reset_email_failed",
                        request=request,
                        severity="error",
                        email=email,
                        error=str(exc),
                    )
            messages.success(request, "Si un compte existe avec cet email, un email de reinitialisation a ete envoye.")
        else:
            emit_event("auth.password_reset_invalid_email", request=request, raw_email=email_raw)
            messages.error(request, "Email invalide.")

    return render(request, "web/auth/reset_password_request.html", {
        "submitted": submitted,
        "reset_link": reset_link if settings.DEBUG else "",
    })


def reset_password_confirm_view(request, uidb64, token):
    user = None
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.filter(pk=uid).first()
    except (TypeError, ValueError, OverflowError):
        user = None

    if not user or not default_token_generator.check_token(user, token):
        messages.error(request, "Lien de reinitialisation invalide ou expire.")
        return redirect("/forgot-password/")

    if request.method == "POST":
        form = SetPasswordForm(user, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Mot de passe mis a jour. Connecte-toi.")
            return redirect("/connexion/")
    else:
        form = SetPasswordForm(user)

    for field in form.fields.values():
        field.widget.attrs.update(
            {
                "style": "width:100%;padding:0.65rem;border-radius:10px;border:1px solid rgba(255,255,255,0.16);background:rgba(255,255,255,0.02);color:#fff;font-size:0.82rem",
            }
        )

    return render(request, "web/auth/reset_password_confirm.html", {
        "form": form,
    })


@require_POST
def logout_view(request):
    logout(request)
    return redirect("/")


# ──────────────────────────────────────────────────────────────────────────────
# Sorties
# ──────────────────────────────────────────────────────────────────────────────

def sorties_list(request):
    professional_redirect = _redirect_professional_account(request)
    if professional_redirect:
        return professional_redirect

    qs = (
        Sortie.objects.all()
        .select_related("creator")
        .annotate(participant_count=Count("participants"))
        .filter(type=Sortie.Type.COMMUNAUTAIRE)
        .filter(is_free=True)
        .order_by("-created_at")
    )
    q = request.GET.get("q", "")
    city = request.GET.get("city", "")
    type_ = Sortie.Type.COMMUNAUTAIRE
    free = "1"
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if city:
        qs = qs.filter(city__icontains=city)

    hero_sortie = qs.exclude(cover_image_url="").first() or qs.first()

    total_count = qs.count()
    member_count = qs.filter(type=Sortie.Type.COMMUNAUTAIRE).count()
    partner_count = 0

    member_sorties = []
    partner_sorties = []
    is_all_types = False

    paginator = Paginator(qs, 18)
    page_obj = paginator.get_page(request.GET.get("page"))
    _attach_sorties_organizer_identity(page_obj.object_list)
    sorties = page_obj
    is_paginated = paginator.num_pages > 1

    return render(request, "web/sorties/list.html", {
        "sorties": sorties,
        "member_sorties": member_sorties,
        "partner_sorties": partner_sorties,
        "is_all_types": is_all_types,
        "hero_sortie": hero_sortie,
        "page_obj": page_obj,
        "is_paginated": is_paginated,
        "total_count": total_count,
        "member_count": member_count,
        "partner_count": partner_count,
        "page_title": "Sorties",
        "page_kicker": "Sorties curatées",
        "page_heading": "Les sorties à rejoindre ce soir.",
        "page_description": "Une lecture plus simple et plus éditoriale des sorties entre membres gratuites, pour comprendre l’ambiance et décider plus vite.",
        "is_activities_page": False,
        "is_partner_only_page": False,
        "is_member_only_page": True,
        "list_base_path": "/sorties/",
        "sortie_detail_base_path": "/sorties/",
        "create_sortie_base_path": "/sorties/creer/",
    })


def sortie_detail(request, pk):
    professional_redirect = _redirect_professional_account(request)
    if professional_redirect:
        return professional_redirect

    sortie = get_object_or_404(Sortie, pk=pk)
    participants = SortieParticipant.objects.filter(sortie=sortie).select_related("user")
    is_participant = request.user.is_authenticated and participants.filter(user=request.user).exists()
    return render(request, "web/sorties/detail.html", {
        "sortie": sortie,
        "participants": participants,
        "participant_count": participants.count(),
        "is_participant": is_participant,
    })


@login_required
def sortie_create(request):
    from apps.sorties.models import Sortie

    partners = Partner.objects.filter(status=Partner.Status.ACTIVE, is_verified=True).order_by("name")

    def _parse_coord(raw_value, min_value, max_value):
        value = (raw_value or "").strip()
        if not value:
            return None
        try:
            parsed = Decimal(value)
            parsed_float = float(parsed)
        except (TypeError, ValueError, InvalidOperation):
            return "invalid"
        if parsed_float < min_value or parsed_float > max_value:
            return "invalid"
        return parsed

    def _parse_datetime(raw_value):
        value = (raw_value or "").strip()
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return "invalid"
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed

    errors = {}
    form_data = {
        "title": (request.GET.get("title") or "").strip(),
        "city": (request.GET.get("city") or "").strip(),
        "location": (request.GET.get("location") or "").strip(),
        "cover_image_url": (request.GET.get("cover_image_url") or "").strip(),
        "starts_at": (request.GET.get("starts_at") or "").strip(),
        "ends_at": (request.GET.get("ends_at") or "").strip(),
        "type": (request.GET.get("type") or Sortie.Type.COMMUNAUTAIRE).strip(),
        "is_free": True,
        "price": "0",
    }
    if request.method == "POST":
        form_data = request.POST
        title = request.POST.get("title", "").strip()
        city = request.POST.get("city", "").strip()
        location = request.POST.get("location", "").strip()
        cover_image_url = request.POST.get("cover_image_url", "").strip()
        cover_image_file = request.FILES.get("cover_image_file")
        latitude = _parse_coord(request.POST.get("latitude"), -90.0, 90.0)
        longitude = _parse_coord(request.POST.get("longitude"), -180.0, 180.0)
        starts_at = _parse_datetime(request.POST.get("starts_at"))
        ends_at = _parse_datetime(request.POST.get("ends_at"))
        type_ = request.POST.get("type", Sortie.Type.COMMUNAUTAIRE)
        partner_id = (request.POST.get("partner_id") or "").strip()
        is_free_raw = bool(request.POST.get("is_free"))
        price_raw = (request.POST.get("price") or "0").strip()

        if not title:
            errors["title"] = "Le titre est requis."
        if not city:
            errors["city"] = "La ville est requise."
        if latitude == "invalid":
            errors["latitude"] = "Latitude invalide."
        if longitude == "invalid":
            errors["longitude"] = "Longitude invalide."
        if starts_at == "invalid":
            errors["starts_at"] = "Heure de début invalide."
        if ends_at == "invalid":
            errors["ends_at"] = "Heure de fin invalide."
        if starts_at not in (None, "invalid") and ends_at not in (None, "invalid") and ends_at <= starts_at:
            errors["ends_at"] = "L'heure de fin doit être après l'heure de début."
        if type_ not in (Sortie.Type.COMMUNAUTAIRE, Sortie.Type.PARTENAIRE):
            errors["type"] = "Seuls les types entre membres et partenaire sont autorisés."
        if cover_image_file:
            content_type = (getattr(cover_image_file, "content_type", "") or "").lower()
            if not content_type.startswith("image/"):
                errors["cover_image_url"] = "Le fichier photo doit être une image."

        selected_partner = None
        if type_ == Sortie.Type.PARTENAIRE:
            if not partner_id:
                errors["partner_id"] = "Sélectionne un partenaire référencé."
            else:
                selected_partner = partners.filter(pk=partner_id).first()
                if selected_partner is None:
                    errors["partner_id"] = "Le partenaire sélectionné est invalide."

        if type_ == Sortie.Type.COMMUNAUTAIRE:
            is_free = True
            price_cents = 0
        else:
            is_free = is_free_raw
            if is_free:
                price_cents = 0
            else:
                try:
                    price_euros = Decimal(price_raw)
                    if price_euros <= 0:
                        errors["price"] = "Le prix doit être supérieur à 0 pour une sortie payante."
                    price_cents = int(price_euros * 100)
                except (InvalidOperation, ValueError):
                    errors["price"] = "Le prix est invalide."
                    price_cents = 0

        if not errors:
            import re
            slug = re.sub(r"[^\w-]", "-", title.lower())[:80]
            if cover_image_file:
                file_name = (cover_image_file.name or "photo.jpg").strip()
                extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else "jpg"
                if extension not in {"jpg", "jpeg", "png", "webp", "gif"}:
                    extension = "jpg"
                media_path = f"sorties/covers/{timezone.now():%Y/%m}/{uuid4().hex}.{extension}"
                stored_path = default_storage.save(media_path, cover_image_file)
                media_url = f"{settings.MEDIA_URL}{stored_path}"
                app_base_url = (getattr(settings, "APP_BASE_URL", "") or "").rstrip("/")
                if app_base_url:
                    cover_image_url = f"{app_base_url}{media_url}"
                else:
                    cover_image_url = request.build_absolute_uri(media_url)
            try:
                sortie = Sortie.objects.create(
                    title=title,
                    slug=slug,
                    description=request.POST.get("description", ""),
                    city=city,
                    location=location,
                    latitude=latitude if latitude != "invalid" else None,
                    longitude=longitude if longitude != "invalid" else None,
                    type=type_,
                    partner=selected_partner,
                    is_free=is_free,
                    price=price_cents,
                    cover_image_url=cover_image_url,
                    max_participants=request.POST.get("max_participants") or None,
                    starts_at=starts_at if starts_at != "invalid" else None,
                    ends_at=ends_at if ends_at != "invalid" else None,
                    creator=request.user,
                )
            except ValidationError as exc:
                for field, field_errors in exc.message_dict.items():
                    errors[field] = " ".join(field_errors)
            else:
                if selected_partner and selected_partner.owner_id:
                    starts_at = sortie.starts_at or timezone.now()
                    PartnerAgendaEntry.objects.create(
                        owner=selected_partner.owner,
                        partner=selected_partner,
                        source=PartnerAgendaEntry.Source.MOOVIOGO,
                        reservation_kind=_reservation_kind_from_partner(selected_partner),
                        status=PartnerAgendaEntry.Status.PENDING,
                        title=f"Sortie Mooviogo - {sortie.title}",
                        customer_name=request.user.display_name or request.user.username,
                        customer_contact=request.user.email,
                        party_size=sortie.max_participants,
                        starts_at=starts_at,
                        linked_sortie=sortie,
                        created_by_user=request.user,
                        notes="Demande creee depuis Mooviogo. En attente de validation partenaire.",
                    )
                    if selected_partner.owner.email:
                        try:
                            send_notification_task.delay(
                                "email",
                                selected_partner.owner.email,
                                (
                                    "Nouvelle demande Mooviogo en attente: "
                                    f"{sortie.title}. Ouvre /partner/agenda/ pour valider la reservation."
                                ),
                                subject="Nouvelle reservation Mooviogo a valider",
                            )
                        except Exception:
                            # Keep sortie creation non-blocking if async broker is unavailable in dev.
                            pass
                messages.success(request, "Sortie créée avec succès !")
                return redirect(f"/sorties/{sortie.pk}/")
    return render(request, "web/sorties/create.html", {
        "form": type("F", (), form_data)(),
        "errors": errors,
        "partners": partners,
        "ui_revision": _ui_revision_tag(),
    })


@login_required
@require_POST
def sortie_join(request, pk):
    sortie = get_object_or_404(Sortie, pk=pk)
    if sortie.status == Sortie.Status.OPEN:
        SortieParticipant.objects.get_or_create(sortie=sortie, user=request.user)

        # Workflow: joining a sortie also adds the user to the sortie group chat.
        chat, _ = Chat.objects.get_or_create(
            type=Chat.Type.GROUP,
            sortie_id=sortie.id,
            defaults={"name": f"Sortie: {sortie.title}", "created_by": sortie.creator},
        )
        ChatParticipant.objects.get_or_create(chat=chat, user=request.user)

        messages.success(request, f"Tu as rejoint « {sortie.title} » !")
    else:
        messages.error(request, "Cette sortie n'est plus disponible.")
    return redirect(f"/sorties/{pk}/")


@login_required
@require_POST
def sortie_leave(request, pk):
    sortie = get_object_or_404(Sortie, pk=pk)
    SortieParticipant.objects.filter(sortie=sortie, user=request.user).delete()
    messages.success(request, f"Tu as quitté « {sortie.title} ».")
    return redirect(f"/sorties/{pk}/")


# ──────────────────────────────────────────────────────────────────────────────
# Restaurants
# ──────────────────────────────────────────────────────────────────────────────

def restaurants_list(request):
    professional_redirect = _redirect_professional_account(request)
    if professional_redirect:
        return professional_redirect

    qs = RestaurantVenue.objects.filter(is_active=True)
    q = request.GET.get("q", "")
    city = request.GET.get("city", "")

    def _apply_city_filter(base_qs, city_value):
        normalized_city = (city_value or "").strip()
        if not normalized_city:
            return base_qs
        normalized_slug = slugify(normalized_city)
        city_lookup = Q(city_label__icontains=normalized_city)
        if normalized_slug:
            city_lookup |= Q(city_slug__icontains=normalized_slug)
        return base_qs.filter(city_lookup)

    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
    if city:
        qs = _apply_city_filter(qs, city)

    ordered_qs = qs.order_by("name")
    city_scope = city or (request.user.city if request.user.is_authenticated else "")
    featured_restaurant = ordered_qs.first()
    featured_is_promoted = False

    if city_scope:
        now = timezone.now()
        promoted_restaurant = (
            _apply_city_filter(ordered_qs, city_scope)
            .filter(
                editorial_boost_starts_at__isnull=False,
                editorial_boost_ends_at__isnull=False,
                editorial_boost_starts_at__lte=now,
                editorial_boost_ends_at__gte=now,
            )
            .order_by("-editorial_boost_amount", "-editorial_boost_ends_at", "name")
            .first()
        )
        if promoted_restaurant:
            featured_restaurant = promoted_restaurant
            featured_is_promoted = True

    paginator = Paginator(ordered_qs, 18)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "web/restaurants/list.html", {
        "venues": page_obj,
        "page_obj": page_obj,
        "is_paginated": paginator.num_pages > 1,
        "featured_restaurant": featured_restaurant,
        "featured_is_promoted": featured_is_promoted,
    })


def restaurant_detail(request, city_slug, slug):
    preview_public = request.GET.get("as_public") == "1"
    if not preview_public:
        professional_redirect = _redirect_professional_account(request)
        if professional_redirect:
            return professional_redirect

    venue = get_object_or_404(RestaurantVenue, city_slug=city_slug, slug=slug)
    is_owner_preview = request.user.is_authenticated and venue.owner_id == request.user.id
    _ensure_upcoming_slots_for_venue(venue)
    today = timezone.localdate()
    slots = RestaurantTimeSlot.objects.filter(
        venue=venue,
        date__gte=today,
        status=RestaurantTimeSlot.SlotStatus.OPEN,
    ).order_by("date", "time")[:20]

    gallery_photos = list(
        RestaurantVenuePhoto.objects.filter(venue=venue, is_active=True)
        .order_by("position", "id")
        .values("image_url", "caption")
    )
    if not gallery_photos and venue.cover_image_url:
        gallery_photos = [{"image_url": venue.cover_image_url, "caption": ""}]
    preview_photos = list(gallery_photos[:4])
    if preview_photos:
        while len(preview_photos) < 4:
            preview_photos.append(preview_photos[len(preview_photos) % len(preview_photos)])

    city_venues = []
    for item in (
        RestaurantVenue.objects.filter(city_slug=venue.city_slug, is_active=True)
        .order_by("name")
        .values("name", "slug", "city_slug", "city_label", "address", "cuisine_type")
    ):
        city_label = item.get("city_label") or venue.city_label or venue.city_slug
        full_address = (item.get("address") or "").strip()
        if full_address:
            full_address = f"{full_address}, {city_label}"
        else:
            full_address = city_label

        city_venues.append(
            {
                "name": item.get("name") or "",
                "slug": item.get("slug") or "",
                "city_slug": item.get("city_slug") or venue.city_slug,
                "city_label": city_label,
                "address": item.get("address") or "",
                "full_address": full_address,
                "cuisine_type": item.get("cuisine_type") or "",
                "is_current": item.get("slug") == venue.slug,
            }
        )

    return render(request, "web/restaurants/detail.html", {
        "venue": venue,
        "slots": slots,
        "highlight_photos": preview_photos,
        "gallery_photos_count": len(gallery_photos),
        "city_venues": city_venues,
        "is_owner_preview": is_owner_preview,
    })


def restaurant_photos(request, city_slug, slug):
    professional_redirect = _redirect_professional_account(request)
    if professional_redirect:
        return professional_redirect

    venue = get_object_or_404(RestaurantVenue, city_slug=city_slug, slug=slug)
    gallery_photos = list(
        RestaurantVenuePhoto.objects.filter(venue=venue, is_active=True)
        .order_by("position", "id")
        .values("image_url", "caption")
    )
    if not gallery_photos and venue.cover_image_url:
        gallery_photos = [{"image_url": venue.cover_image_url, "caption": ""}]

    return render(request, "web/restaurants/gallery.html", {
        "venue": venue,
        "gallery_photos": gallery_photos,
    })


@login_required
@require_POST
def restaurant_book(request, city_slug, slug):
    venue = get_object_or_404(RestaurantVenue, city_slug=city_slug, slug=slug)
    slot_id = request.POST.get("slot_id")
    slot = get_object_or_404(RestaurantTimeSlot, pk=slot_id, venue=venue)
    if slot.date < timezone.localdate() or slot.status != RestaurantTimeSlot.SlotStatus.OPEN:
        messages.error(request, "Ce créneau n'est plus réservable.")
        return redirect(f"/restaurants/{city_slug}/{slug}/")

    already_booked = Booking.objects.filter(user=request.user, restaurant_slot_id=slot.id).exists()
    if already_booked:
        messages.info(request, "Tu as déjà une réservation sur ce créneau.")
        return redirect(f"/restaurants/{city_slug}/{slug}/")

    if slot.confirmed_count < slot.capacity:
        booking_status = Booking.Status.CONFIRMED
        if venue.reservation_mode == RestaurantVenue.ReservationMode.MANUAL:
            booking_status = Booking.Status.PENDING

        Booking.objects.create(
            user=request.user,
            booking_type=Booking.BookingType.RESTAURANT,
            restaurant_slot_id=slot.id,
            status=booking_status,
        )

        if booking_status == Booking.Status.CONFIRMED:
            slot.confirmed_count += 1
            slot.save(update_fields=["confirmed_count"])
            messages.success(request, "Réservation confirmée !")
        else:
            messages.success(request, "Demande envoyée au restaurant. En attente de validation.")
    else:
        messages.error(request, "Ce créneau est complet.")
    return redirect(f"/restaurants/{city_slug}/{slug}/")


@login_required
@require_POST
def partner_restaurant_booking_decision(request, booking_id):
    if not _is_professional_account(request.user):
        messages.error(request, "Accès réservé aux partenaires.")
        return redirect("/devenir-partenaire/")

    action = (request.POST.get("action") or "").strip().lower()
    if action not in {"confirm", "reject"}:
        messages.error(request, "Action invalide.")
        return redirect("/partner/bookings/")

    booking = get_object_or_404(Booking, pk=booking_id, booking_type=Booking.BookingType.RESTAURANT)
    if not booking.restaurant_slot_id:
        messages.error(request, "Réservation restaurant introuvable.")
        return redirect("/partner/bookings/")

    slot = RestaurantTimeSlot.objects.filter(pk=booking.restaurant_slot_id).select_related("venue").first()
    if not slot or slot.venue.owner_id != request.user.id:
        messages.error(request, "Cette réservation ne t'appartient pas.")
        return redirect("/partner/bookings/")

    if booking.status != Booking.Status.PENDING:
        messages.info(request, "Cette demande est déjà traitée.")
        return redirect("/partner/bookings/")

    if action == "reject":
        booking.status = Booking.Status.CANCELLED
        booking.save(update_fields=["status", "updated_at"])
        messages.success(request, "Demande refusée.")
        return redirect("/partner/bookings/")

    if slot.status != RestaurantTimeSlot.SlotStatus.OPEN or slot.date < timezone.localdate():
        messages.error(request, "Impossible de valider: créneau fermé ou expiré.")
        return redirect("/partner/bookings/")

    if slot.confirmed_count >= slot.capacity:
        booking.status = Booking.Status.CANCELLED
        booking.save(update_fields=["status", "updated_at"])
        messages.error(request, "Créneau complet: demande refusée automatiquement.")
        return redirect("/partner/bookings/")

    booking.status = Booking.Status.CONFIRMED
    booking.save(update_fields=["status", "updated_at"])
    slot.confirmed_count += 1
    slot.save(update_fields=["confirmed_count"])
    messages.success(request, "Réservation validée.")
    return redirect("/partner/bookings/")


# ──────────────────────────────────────────────────────────────────────────────
# Events
# ──────────────────────────────────────────────────────────────────────────────

def evenements_list(request):
    professional_redirect = _redirect_professional_account(request)
    if professional_redirect:
        return professional_redirect

    events = Event.objects.filter(
        status=Event.Status.PUBLISHED,
        is_partner_event=False,
    ).exclude(
        slug="apero-reseau-mooviogo-bordeaux",
    ).order_by("starts_at")
    return render(request, "web/evenements/list.html", {"events": events})


def evenement_detail(request, slug):
    professional_redirect = _redirect_professional_account(request)
    if professional_redirect:
        return professional_redirect

    event = get_object_or_404(Event, slug=slug, status=Event.Status.PUBLISHED)
    return render(request, "web/evenements/detail.html", {"event": event})


def events_alias(request):
    return evenements_list(request)


# ──────────────────────────────────────────────────────────────────────────────
# Villes
# ──────────────────────────────────────────────────────────────────────────────

def villes_list(request):
    professional_redirect = _redirect_professional_account(request)
    if professional_redirect:
        return professional_redirect

    city_map = {}

    def ensure_city(slug, name):
        if not slug:
            return None
        key = slug.strip().lower()
        if key not in city_map:
            city_map[key] = {
                "name": name,
                "slug": key,
                "sortie_count": 0,
                "event_count": 0,
                "restaurant_count": 0,
            }
        elif name and not city_map[key]["name"]:
            city_map[key]["name"] = name
        return city_map[key]

    sortie_counts = (
        Sortie.objects.filter(status=Sortie.Status.OPEN)
        .values("city")
        .annotate(count=Count("id"))
    )
    for row in sortie_counts:
        city_name = (row.get("city") or "").strip()
        if not city_name:
            continue
        slug = city_name.lower().replace(" ", "-")
        city_entry = ensure_city(slug, city_name)
        if city_entry:
            city_entry["sortie_count"] = row.get("count", 0)

    event_counts = (
        Event.objects.filter(status=Event.Status.PUBLISHED)
        .values("city")
        .annotate(count=Count("id"))
    )
    for row in event_counts:
        city_name = (row.get("city") or "").strip()
        if not city_name:
            continue
        slug = city_name.lower().replace(" ", "-")
        city_entry = ensure_city(slug, city_name)
        if city_entry:
            city_entry["event_count"] = row.get("count", 0)

    restaurant_counts = (
        RestaurantVenue.objects.filter(is_active=True)
        .values("city_slug", "city_label")
        .annotate(count=Count("id"))
    )
    for row in restaurant_counts:
        slug = (row.get("city_slug") or "").strip().lower()
        city_name = (row.get("city_label") or slug.replace("-", " ").title()).strip()
        city_entry = ensure_city(slug, city_name)
        if city_entry:
            city_entry["restaurant_count"] = row.get("count", 0)

    cities = sorted(
        city_map.values(),
        key=lambda item: (
            item["sortie_count"] + item["event_count"] + item["restaurant_count"],
            item["name"],
        ),
        reverse=True,
    )
    return render(request, "web/villes/list.html", {"cities": cities})


def ville_detail(request, city_slug):
    professional_redirect = _redirect_professional_account(request)
    if professional_redirect:
        return professional_redirect

    city_name = city_slug.replace("-", " ").title()
    sorties = Sortie.objects.filter(status=Sortie.Status.OPEN, city__iexact=city_name).order_by("-created_at")[:6]
    restaurants = RestaurantVenue.objects.filter(is_active=True, city_slug=city_slug)[:6]
    events = Event.objects.filter(status=Event.Status.PUBLISHED, city__iexact=city_name).order_by("starts_at")[:6]
    return render(request, "web/villes/detail.html", {
        "city_name": city_name,
        "city_slug": city_slug,
        "sorties": sorties,
        "restaurants": restaurants,
        "events": events,
        "active_tab": "all",
    })


# ──────────────────────────────────────────────────────────────────────────────
# Partners
# ──────────────────────────────────────────────────────────────────────────────

def partenaires_list(request):
    professional_redirect = _redirect_professional_account(request)
    if professional_redirect:
        return professional_redirect

    qs = Partner.objects.filter(status=Partner.Status.ACTIVE).select_related("owner")
    cat = request.GET.get("categorie", "").strip()
    if cat:
        qs = qs.filter(category=cat)
    categories = (
        Partner.objects.filter(status=Partner.Status.ACTIVE)
        .exclude(category="")
        .values_list("category", flat=True)
        .distinct()
        .order_by("category")
    )
    return render(request, "web/partenaires/list.html", {"partners": qs, "categories": categories})


def partenaire_public_page(request, slug):
    partner = Partner.objects.filter(slug=slug).select_related("owner").first()
    if not partner:
        return render(request, "web/platform/simple_page.html", {
            "title": "Page publique partenaire",
            "subtitle": "Introuvable",
            "description": "Cette page partenaire n'existe pas.",
        }, status=404)

    is_owner = request.user.is_authenticated and partner.owner_id == request.user.id
    if partner.status != Partner.Status.ACTIVE and not is_owner:
        return render(request, "web/platform/simple_page.html", {
            "title": "Page publique partenaire",
            "subtitle": "Indisponible",
            "description": "Cette page partenaire n'est pas disponible publiquement.",
        }, status=404)

    return render(request, "web/partenaires/public_detail.html", {
        "partner": partner,
        "is_owner_preview": is_owner,
    })


def devenir_partenaire(request):
    return render(request, "web/devenir_partenaire.html")


def devenir_partenaire_offre(request, offre_slug):
    offres = {
        "restaurant": {
            "label": "Restaurant",
            "subtitle": "Tout ce que couvre l'offre restaurant, detaille par niveau",
            "plans": [
                {
                    "name": "Offre 1 - Starter",
                    "price": "Gratuit",
                    "items": [
                        "Commission: 3 EUR HT par reservation",
                        "Reservation: systeme reservation, gestion tables, disponibilites, confirmations",
                        "Dashboard: reservations, statistiques simples, historique clients",
                        "Menus: QR code, menu digital, photos",
                        "Notifications: email, push reservation",
                        "Visibilite plateforme: referencement local, geolocalisation",
                    ],
                },
                {
                    "name": "Offre 2 - Pro IA",
                    "price": "149 EUR / mois HT",
                    "items": [
                        "Commission: 2 EUR HT par reservation",
                        "Inclus: IA no-show",
                        "Inclus: IA marketing",
                        "Inclus: CRM",
                        "Inclus: WhatsApp",
                        "Inclus: analytics",
                        "Inclus: menus IA",
                        "Inclus: automatisations",
                    ],
                },
            ],
        },
        "nightlife": {
            "label": "Nightlife",
            "subtitle": "Tout ce que couvre l'offre nightlife, detaille par niveau",
            "plans": [
                {
                    "name": "Offre 1 - Starter",
                    "price": "49 EUR / mois HT",
                    "items": [
                        "Cibles: discotheques, bars, rooftops, concerts, festivals, pubs",
                        "Commission: 1 EUR a 2 EUR par billet vendu",
                        "Publication evenements: creation de soirees, affiches, galerie photos, videos",
                        "Billetterie: QR codes, scan entree, validation mobile",
                        "Gestion participants: liste invites, statistiques simples, capacite evenements",
                        "Paiements: Stripe, Apple Pay, Google Pay",
                        "Dashboard nightlife: ventes, remplissage, participants",
                    ],
                },
                {
                    "name": "Offre 2 - Pro IA",
                    "price": "149 EUR / mois HT",
                    "items": [
                        "Commission: 2 EUR par billet vendu",
                        "Inclus tout BASIC +",
                        "IA Nightlife: generation automatique d'affiches evenements, posts Instagram, stories, videos TikTok, hashtags",
                        "IA Marketing: relance participants, campagnes ciblees, notifications intelligentes, push geolocalisees",
                        "Sponsorisation automatique: mise en avant plateforme, visibilite homepage, boost decouverte",
                        "Analytics avancees (KPIs): frequentation, revenus, taux conversion, evenements performants, engagement utilisateurs",
                        "WhatsApp Business: confirmations, billets, assistance participants",
                        "Support VIP: support prioritaire, onboarding personnalise",
                    ],
                },
            ],
        },
        "activite": {
            "label": "Activite",
            "subtitle": "Tout ce que couvre l'offre activite, detaille par niveau",
            "plans": [
                {
                    "name": "Offre 1 - Starter",
                    "price": "29 EUR / mois HT",
                    "items": [
                        "Cibles: karting, paintball, bowling, escape game, laser game, activites sportives, loisirs",
                        "Commission: 10% par reservation payante",
                        "Profil partenaire: fiche etablissement, logo, photos, description, horaires, coordonnees",
                        "Gestion reservations: reception des demandes, accepter/refuser, gestion participants, historique",
                        "Paiements: Stripe integre, paiements securises, acomptes possibles",
                        "Dashboard simple: reservations du jour, revenus, statistiques basiques",
                        "Billetterie: QR codes, validation entree, liste participants",
                        "Support: support email standard",
                    ],
                },
                {
                    "name": "Offre 2 - Pro IA",
                    "price": "79 EUR / mois HT",
                    "items": [
                        "Commission: 12% par reservation payante",
                        "Inclus tout Starter +",
                        "IA Marketing: generation automatique de posts Instagram, hashtags, descriptions evenements, textes promotionnels",
                        "IA Campagnes: relance clients absents, promotions heures creuses, campagnes automatiques, notifications intelligentes",
                        "Analytics avancees (KPIs): frequentation, conversion, taux de remplissage, heures rentables, clients recurrents",
                        "Notifications avancees: push, SMS, WhatsApp",
                        "Mise en avant partenaire: meilleure visibilite plateforme, boost decouverte locale",
                        "Support prioritaire: reponse acceleree, assistance onboarding",
                    ],
                },
            ],
        },
    }

    offre = offres.get(offre_slug)
    if not offre:
        return redirect("devenir-partenaire")

    return render(request, "web/devenir_partenaire_offre.html", {
        "offre": offre,
        "offre_slug": offre_slug,
    })


@login_required
def messages_page(request):
    chats = Chat.objects.filter(participants__user=request.user).distinct().prefetch_related("participants", "messages")
    return render(request, "web/platform/messages.html", {
        "chats": chats,
    })


@login_required
def notifications_page(request):
    return render(request, "web/platform/simple_page.html", {
        "title": "Notifications",
        "subtitle": "Alertes en temps reel",
        "description": "Rappels d'evenements, confirmations de reservation, promotions et activites locales.",
        "actions": [
            {"href": "/settings/", "label": "Regler mes notifications"},
            {"href": "/explore/", "label": "Explorer"},
        ],
    })


@login_required
def favorites_page(request):
    recent_sorties = Sortie.objects.filter(participants__user=request.user).distinct().order_by("-created_at")[:8]
    return render(request, "web/platform/simple_page.html", {
        "title": "Favoris",
        "subtitle": "Sorties et lieux sauvegardes",
        "description": "Conserve toutes tes sorties preferees et les lieux a ne pas manquer.",
        "items": [s.title for s in recent_sorties],
        "actions": [
            {"href": "/explore/", "label": "Ajouter des favoris"},
        ],
    })


@login_required
def my_events_page(request):
    created_sorties = Sortie.objects.filter(creator=request.user).order_by("-created_at")[:12]
    joined_sorties = Sortie.objects.filter(participants__user=request.user).distinct().order_by("-created_at")[:12]
    return render(request, "web/platform/my_events.html", {
        "created_sorties": created_sorties,
        "joined_sorties": joined_sorties,
    })


@login_required
def my_tickets_page(request):
    bookings = Booking.objects.filter(user=request.user).order_by("-created_at")[:20]
    payments = Payment.objects.filter(user=request.user).order_by("-created_at")[:20]
    tickets = Ticket.objects.filter(user=request.user).order_by("-created_at")[:20]
    return render(request, "web/platform/my_tickets.html", {
        "bookings": bookings,
        "payments": payments,
        "tickets": tickets,
    })


@login_required
def settings_page(request):
    return profil_modifier(request)


@login_required
def create_free_event(request):
    return sortie_create(request)


@login_required
def create_activity_request(request):
    errors = {}
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        city = request.POST.get("city", "").strip()
        description = request.POST.get("description", "").strip()
        category = request.POST.get("category", "").strip()

        if not title:
            errors["title"] = "Le titre est obligatoire."
        if not city:
            errors["city"] = "La ville est obligatoire."

        if not errors:
            PartnerOpportunity.objects.create(
                title=title,
                city=city,
                description=description,
                category=category,
                status=PartnerOpportunity.Status.OPEN,
            )
            messages.success(request, "Demande d'activite envoyee aux partenaires.")
            return redirect("/activities/")

    return render(request, "web/platform/activity_request.html", {"errors": errors})


# ──────────────────────────────────────────────────────────────────────────────
# Profil
# ──────────────────────────────────────────────────────────────────────────────

@login_required
def profil(request):
    created_sorties_qs = (
        Sortie.objects.filter(creator=request.user)
        .annotate(participant_count=Count("participants"))
        .order_by("-created_at")
    )
    participations_qs = (
        SortieParticipant.objects.filter(user=request.user)
        .select_related("sortie")
        .order_by("-joined_at")
    )
    confirmed_bookings_qs = Booking.objects.filter(
        user=request.user,
        status=Booking.Status.CONFIRMED,
    ).order_by("-created_at")
    active_tickets_qs = Ticket.objects.filter(
        user=request.user,
        status=Ticket.Status.ACTIVE,
    ).order_by("-created_at")

    my_sorties = list(created_sorties_qs[:6])
    my_participations = list(participations_qs[:4])

    city = (request.user.city or "").strip()
    nearby_sorties_qs = Sortie.objects.filter(status=Sortie.Status.OPEN)
    nearby_events_qs = Event.objects.filter(status=Event.Status.PUBLISHED)
    nearby_members_qs = SortieParticipant.objects.filter(sortie__status=Sortie.Status.OPEN)

    if city:
        nearby_sorties_qs = nearby_sorties_qs.filter(city__iexact=city)
        nearby_events_qs = nearby_events_qs.filter(city__iexact=city)
        nearby_members_qs = nearby_members_qs.filter(sortie__city__iexact=city)

    return render(request, "web/profil/profil.html", {
        "my_sorties": my_sorties,
        "my_participations": my_participations,
        "profile_stats": {
            "created_sorties_count": created_sorties_qs.count(),
            "joined_sorties_count": participations_qs.count(),
            "confirmed_bookings_count": confirmed_bookings_qs.count(),
            "active_tickets_count": active_tickets_qs.count(),
        },
        "profile_highlights": {
            "recent_sortie": my_sorties[0] if my_sorties else None,
            "recent_participation": my_participations[0] if my_participations else None,
            "recent_booking": confirmed_bookings_qs.first(),
            "recent_ticket": active_tickets_qs.first(),
        },
        "community_snapshot": {
            "city_label": city or "Ta zone",
            "open_sorties_count": nearby_sorties_qs.count(),
            "published_events_count": nearby_events_qs.count(),
            "active_members_count": nearby_members_qs.values("user_id").distinct().count(),
        },
    })


@login_required
def profil_modifier(request):
    if request.method == "POST":
        user = request.user
        user.display_name = request.POST.get("display_name", "").strip() or user.display_name
        user.bio = request.POST.get("bio", "").strip()
        user.city = request.POST.get("city", "").strip()
        avatar_url = request.POST.get("avatar_url", "").strip()
        if avatar_url:
            user.avatar_url = avatar_url
        user.save(update_fields=["display_name", "bio", "city", "avatar_url"])
        messages.success(request, "Profil mis à jour.")
        return redirect("/profil/")
    return render(request, "web/profil/modifier.html")


@login_required
def profil_reservations(request):
    bookings = Booking.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "web/profil/reservations.html", {"bookings": bookings})


# ──────────────────────────────────────────────────────────────────────────────
# Partner dashboard
# ──────────────────────────────────────────────────────────────────────────────

@login_required
def partenaire_dashboard(request):
    if not _is_professional_account(request.user):
        messages.error(request, "Accès réservé aux partenaires.")
        return redirect("/devenir-partenaire/")

    partner_profile = Partner.objects.filter(owner=request.user).first()
    detected_section = _normalize_dashboard_section(
        _professional_section(
            request.user,
            partner_profile=partner_profile,
            owned_venues=RestaurantVenue.objects.filter(owner=request.user, is_active=True),
        )
    )
    return redirect(f"/partenaire/{detected_section}/")


@login_required
def partenaire_dashboard_section(request, section):
    if not _is_professional_account(request.user):
        messages.error(request, "Accès réservé aux partenaires.")
        return redirect("/devenir-partenaire/")

    partner_profile = Partner.objects.filter(owner=request.user).first()
    public_page = _professional_public_page_payload(request.user)
    assigned_section = _normalize_dashboard_section(
        _professional_section(
            request.user,
            partner_profile=partner_profile,
            owned_venues=RestaurantVenue.objects.filter(owner=request.user, is_active=True),
        )
    )
    requested_section = _normalize_dashboard_section(section)
    if requested_section != assigned_section:
        messages.info(request, "Section verrouillee sur ton type de compte.")
        return redirect(f"/partenaire/{assigned_section}/")

    section_key = assigned_section
    config = _dashboard_section_config(section_key)
    active_offer_key = _resolve_active_offer_key(partner_profile, section_key)
    offers = _build_offers_with_lock(config, active_offer_key)
    now = timezone.localtime()

    establishment_href = "/partner/establishment/"
    establishment_meta = "Page publique visible par les utilisateurs"
    if not public_page["url"]:
        establishment_meta = "Parametres, equipe, branding"

    quick_links = [
        {"href": "/partner/events/", "title": "Evenements", "meta": "Programmation, publication, suivi"},
        {"href": "/partner/agenda/", "title": "Agenda", "meta": "Planning et confirmations"},
        {"href": "/partner/requests/", "title": "Demandes", "meta": "Pipeline entrant"},
        {"href": "/partner/analytics/", "title": "Analytiques", "meta": "KPI, conversion, performance"},
        {"href": "/partner/payments/", "title": "Paiements", "meta": "Encaissements et remboursements"},
        {"href": establishment_href, "title": "Etablissement", "meta": establishment_meta},
    ]

    if public_page["url"]:
        quick_links.append(
            {
                "href": public_page["url"],
                "title": "Page publique",
                "meta": "Voir le profil visible par les clients",
            }
        )

    return render(request, "web/partenaire/dashboard.html", {
        "partner_profile": partner_profile,
        "section_key": section_key,
        "section_label": config["label"],
        "section_headline": config["headline"],
        "section_description": config["description"],
        "section_points": config["hero_points"],
        "offers": offers,
        "active_offer_key": active_offer_key,
        "kpis": _dashboard_kpis_for_section(section_key, request.user, partner_profile),
        "live_examples": _dashboard_live_examples(section_key, now),
        "quick_links": quick_links,
        "public_page_url": public_page["url"],
        "public_page_label": public_page["label"],
    })


@login_required
def partner_events_page(request):
    if not _is_professional_account(request.user):
        return redirect("/devenir-partenaire/")
    partner_events = Event.objects.filter(is_partner_event=True).order_by("-created_at")[:20]
    rows_data = [{"title": e.title, "meta": e.city} for e in partner_events]
    if not rows_data:
        rows_data = _partner_demo_rows("events")

    highlight_blocks = [
        {"label": "Publies", "value": "12", "meta": "visibles cette semaine"},
        {"label": "Brouillons", "value": "4", "meta": "a finaliser"},
        {"label": "Complets", "value": "3", "meta": "taux de remplissage > 95%"},
    ]
    public_page = _professional_public_page_payload(request.user)

    return render(request, "web/platform/dashboard_list.html", {
        "title": "Partner events",
        "subtitle": "Gestion des evenements partenaires (compte actif)",
        "rows_data": rows_data,
        "highlight_blocks": highlight_blocks,
        "public_page_url": public_page["url"],
        "public_page_label": public_page["label"],
    })


@login_required
def partner_bookings_page(request):
    if not _is_professional_account(request.user):
        return redirect("/devenir-partenaire/")
    rows = (
        PartnerAgendaEntry.objects.filter(
            owner=request.user,
            reservation_kind__in={
                PartnerAgendaEntry.ReservationKind.ACTIVITY,
                PartnerAgendaEntry.ReservationKind.OTHER,
            },
        )
        .order_by("-starts_at", "-created_at")[:80]
    )
    rows_data = [
        {
            "title": row.title,
            "meta": f"{timezone.localtime(row.starts_at).strftime('%d/%m %H:%M')} - {row.get_status_display()} - {row.customer_name or 'Client'}",
        }
        for row in rows
    ]
    if not rows_data:
        now = timezone.localtime()
        rows_data = [
            {"title": "Session karting 8 pers.", "meta": f"{(now + timedelta(days=1)).strftime('%d/%m')} 18:30 - En attente - M. Dupont"},
            {"title": "Escape game famille", "meta": f"{(now + timedelta(days=2)).strftime('%d/%m')} 20:00 - Confirmee - Mme Leroy"},
            {"title": "Laser game afterwork", "meta": f"{(now + timedelta(days=3)).strftime('%d/%m')} 19:30 - Confirmee - Team Nova"},
            {"title": "Pack bowling et diner 12 pers.", "meta": f"{(now + timedelta(days=4)).strftime('%d/%m')} 21:00 - En attente - Agence Mistral"},
            {"title": "Session karting junior", "meta": f"{(now + timedelta(days=5)).strftime('%d/%m')} 15:00 - Refusee - Capacite atteinte"},
        ]

    highlight_blocks = [
        {"label": "En attente", "value": "5", "meta": "demandes a traiter"},
        {"label": "Confirmees", "value": "18", "meta": "sur 7 jours"},
        {"label": "Refusees", "value": "2", "meta": "capacite ou indisponibilite"},
    ]
    public_page = _professional_public_page_payload(request.user)

    return render(request, "web/platform/dashboard_list.html", {
        "title": "Reservations activite",
        "subtitle": "Suivi des demandes et confirmations (compte actif)",
        "rows_data": rows_data,
        "highlight_blocks": highlight_blocks,
        "public_page_url": public_page["url"],
        "public_page_label": public_page["label"],
    })


@login_required
def partner_agenda_page(request):
    if not _is_professional_account(request.user):
        return redirect("/devenir-partenaire/")

    partner_profile = Partner.objects.filter(owner=request.user).first()
    activity_offer = _activity_offer_two_details()
    account_section = "activity"
    allowed_kinds = {
        PartnerAgendaEntry.ReservationKind.ACTIVITY,
        PartnerAgendaEntry.ReservationKind.OTHER,
    }
    default_kind = PartnerAgendaEntry.ReservationKind.ACTIVITY

    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        starts_at_raw = (request.POST.get("starts_at") or "").strip()
        reservation_kind = (request.POST.get("reservation_kind") or default_kind).strip()
        customer_name = (request.POST.get("customer_name") or "").strip()
        customer_contact = (request.POST.get("customer_contact") or "").strip()
        notes = (request.POST.get("notes") or "").strip()
        party_size_raw = (request.POST.get("party_size") or "").strip()

        if not title:
            messages.error(request, "Le titre de reservation est requis.")
            return redirect("/partner/agenda/")
        if not starts_at_raw:
            messages.error(request, "La date et l'heure sont requises.")
            return redirect("/partner/agenda/")

        try:
            starts_at = datetime.fromisoformat(starts_at_raw)
            if timezone.is_naive(starts_at):
                starts_at = timezone.make_aware(starts_at, timezone.get_current_timezone())
        except ValueError:
            messages.error(request, "Format de date invalide.")
            return redirect("/partner/agenda/")

        party_size = None
        if party_size_raw:
            try:
                party_size = max(1, int(party_size_raw))
            except ValueError:
                messages.error(request, "Le nombre de participants est invalide.")
                return redirect("/partner/agenda/")

        if reservation_kind not in allowed_kinds:
            reservation_kind = default_kind

        PartnerAgendaEntry.objects.create(
            owner=request.user,
            partner=partner_profile,
            source=PartnerAgendaEntry.Source.DIRECT,
            reservation_kind=reservation_kind,
            status=PartnerAgendaEntry.Status.CONFIRMED,
            title=title,
            customer_name=customer_name,
            customer_contact=customer_contact,
            party_size=party_size,
            starts_at=starts_at,
            notes=notes,
            created_by_user=request.user,
        )
        messages.success(request, "Réservation ajoutée à l'agenda.")
        return redirect("/partner/agenda/")

    agenda_entries = list(
        PartnerAgendaEntry.objects.filter(owner=request.user, reservation_kind__in=allowed_kinds)
        .select_related("linked_sortie", "created_by_user", "partner")
        .order_by("starts_at", "-created_at")[:120]
    )

    booking_rows = []

    combined_items = []
    for entry in agenda_entries:
        combined_items.append({
            "kind": "entry",
            "starts_at": entry.starts_at,
            "status": entry.status,
            "source": entry.source,
            "entry": entry,
        })

    for booking in booking_rows:
        slot = slot_by_id.get(booking.restaurant_slot_id)
        starts_at = timezone.now()
        if slot:
            starts_at = timezone.make_aware(
                datetime.combine(slot.date, slot.time),
                timezone.get_current_timezone(),
            )
        combined_items.append({
            "kind": "booking",
            "starts_at": starts_at,
            "status": booking.status,
            "source": "MOOVIOGO",
            "booking": booking,
            "slot": slot,
        })

    combined_items.sort(key=lambda row: row["starts_at"])

    def _section_from_row(row):
        return "activity"

    today = timezone.localdate()
    try:
        week_offset = int((request.GET.get("week_offset") or "0").strip())
    except ValueError:
        week_offset = 0

    anchor_day = today + timedelta(days=week_offset * 7)
    week_start = anchor_day - timedelta(days=anchor_day.weekday())
    week_end = week_start + timedelta(days=6)

    def _row_to_example(row):
        local_dt = timezone.localtime(row["starts_at"])
        section = _section_from_row(row)
        if row["kind"] == "booking":
            slot = row.get("slot")
            title = slot.venue.name if slot else f"Réservation Mooviogo #{row['booking'].id}"
            customer = row["booking"].user.display_name or row["booking"].user.username
            source = "MOOVIOGO"
        else:
            title = row["entry"].title
            customer = row["entry"].customer_name or "Client"
            source = row["entry"].get_source_display().upper()
        return {
            "title": title,
            "customer": customer,
            "time": local_dt.strftime("%a %d/%m • %H:%M"),
            "status": row["status"],
            "source": source,
            "section": section,
            "starts_at_local": local_dt,
        }

    direct_confirmed = next(
        (
            row for row in combined_items
            if row["kind"] == "entry"
            and row["status"] == PartnerAgendaEntry.Status.CONFIRMED
            and row["source"] == PartnerAgendaEntry.Source.DIRECT
        ),
        None,
    )
    mooviogo_confirmed = next(
        (
            row for row in combined_items
            if row["source"] == "MOOVIOGO"
            and row["status"] == Booking.Status.CONFIRMED
        ),
        None,
    )
    mooviogo_pending = next(
        (
            row for row in combined_items
            if row["source"] == "MOOVIOGO"
            and row["status"] == Booking.Status.PENDING
        ),
        None,
    )

    section_title_by_key = {
        "activity": "Activite",
    }

    example_items = [
        {
            "label": "Réservation directe saisie par le pro",
            "badge": "DIRECT",
            "from_real": bool(direct_confirmed),
            "data": _row_to_example(direct_confirmed) if direct_confirmed else {
                "title": "Session karting entreprise",
                "customer": "Mme Martin",
                "time": (week_start + timedelta(days=3)).strftime("%a %d/%m") + " • 20:30",
                "status": PartnerAgendaEntry.Status.CONFIRMED,
                "source": "DIRECT",
                "section": account_section,
                "starts_at_local": timezone.make_aware(
                    datetime.combine(week_start + timedelta(days=3), datetime.min.time().replace(hour=20, minute=30)),
                    timezone.get_current_timezone(),
                ),
            },
        },
        {
            "label": "Réservation Mooviogo validée par le pro",
            "badge": "MOOVIOGO",
            "from_real": bool(mooviogo_confirmed),
            "data": _row_to_example(mooviogo_confirmed) if mooviogo_confirmed else {
                "title": "Pack laser game groupe",
                "customer": "Lucas Perrin",
                "time": (week_start + timedelta(days=4)).strftime("%a %d/%m") + " • 21:00",
                "status": Booking.Status.CONFIRMED,
                "source": "MOOVIOGO",
                "section": account_section,
                "starts_at_local": timezone.make_aware(
                    datetime.combine(week_start + timedelta(days=4), datetime.min.time().replace(hour=21, minute=0)),
                    timezone.get_current_timezone(),
                ),
            },
        },
        {
            "label": "Réservation Mooviogo en attente de validation",
            "badge": "PENDING",
            "from_real": bool(mooviogo_pending),
            "data": _row_to_example(mooviogo_pending) if mooviogo_pending else {
                "title": "Escape game anniversaire",
                "customer": "Sarah T.",
                "time": (week_start + timedelta(days=5)).strftime("%a %d/%m") + " • 12:00",
                "status": Booking.Status.PENDING,
                "source": "MOOVIOGO",
                "section": account_section,
                "starts_at_local": timezone.make_aware(
                    datetime.combine(week_start + timedelta(days=5), datetime.min.time().replace(hour=12, minute=0)),
                    timezone.get_current_timezone(),
                ),
            },
        },
    ]
    week_days = []
    for offset in range(7):
        current_day = week_start + timedelta(days=offset)
        week_days.append({
            "date": current_day,
            "key": current_day.isoformat(),
            "weekday_label": current_day.strftime("%a"),
            "day_label": current_day.strftime("%d/%m"),
            "is_today": current_day == today,
        })

    hour_slots = list(range(8, 24))
    events_by_slot = defaultdict(list)

    for row in combined_items:
        local_dt = timezone.localtime(row["starts_at"])
        event_day = local_dt.date()
        if event_day < week_start or event_day > week_end:
            continue
        if local_dt.hour < hour_slots[0] or local_dt.hour > hour_slots[-1]:
            continue

        if row["kind"] == "booking":
            slot = row.get("slot")
            title = slot.venue.name if slot else f"Réservation Mooviogo #{row['booking'].id}"
            subtitle = row["booking"].user.display_name or row["booking"].user.username
        else:
            title = row["entry"].title
            subtitle = row["entry"].customer_name or "Client"

        section = _section_from_row(row)

        events_by_slot[(event_day.isoformat(), local_dt.hour)].append({
            "title": title,
            "time": local_dt.strftime("%H:%M"),
            "subtitle": subtitle,
            "status": row["status"],
            "section": section,
        })

    # Ensure sample scenarios are visible in the weekly grid when real data is missing.
    for sample in example_items:
        if sample["from_real"]:
            continue
        local_dt = sample["data"]["starts_at_local"]
        event_day = local_dt.date()
        if event_day < week_start or event_day > week_end:
            continue
        if local_dt.hour < hour_slots[0] or local_dt.hour > hour_slots[-1]:
            continue
        events_by_slot[(event_day.isoformat(), local_dt.hour)].append({
            "title": sample["data"]["title"],
            "time": local_dt.strftime("%H:%M"),
            "subtitle": sample["data"]["customer"],
            "status": sample["data"]["status"],
            "section": sample["data"]["section"],
        })

    for row in combined_items:
        row["section"] = _section_from_row(row)

    week_rows = []
    for hour in hour_slots:
        cells = []
        for day in week_days:
            cells.append({
                "events": events_by_slot.get((day["key"], hour), []),
            })
        week_rows.append({
            "hour_label": f"{hour:02d}:00",
            "cells": cells,
        })

    pending_count = sum(1 for row in combined_items if row["status"] == "PENDING")
    public_page = _professional_public_page_payload(request.user)

    return render(request, "web/partenaire/agenda.html", {
        "title": "Agenda partenaire",
        "subtitle": "Réservations Mooviogo et réservations directes au même endroit.",
        "items": combined_items,
        "week_days": week_days,
        "week_rows": week_rows,
        "week_offset": week_offset,
        "previous_week_offset": week_offset - 1,
        "next_week_offset": week_offset + 1,
        "week_range_label": f"{week_start.strftime('%d/%m')} - {week_end.strftime('%d/%m')}",
        "example_items": example_items,
        "activity_offer": activity_offer,
        "account_section": account_section,
        "account_section_label": section_title_by_key.get(account_section, "Activite"),
        "pending_count": pending_count,
        "public_page_url": public_page["url"],
        "public_page_label": public_page["label"],
    })


@login_required
@require_POST
def partner_agenda_decision(request, entry_id):
    if not _is_professional_account(request.user):
        return redirect("/devenir-partenaire/")

    entry = get_object_or_404(PartnerAgendaEntry, pk=entry_id, owner=request.user)
    action = (request.POST.get("action") or "").strip().lower()

    if action == "confirm":
        entry.status = PartnerAgendaEntry.Status.CONFIRMED
        entry.save(update_fields=["status", "updated_at"])
        messages.success(request, "Réservation validée.")
    elif action in {"reject", "cancel"}:
        entry.status = PartnerAgendaEntry.Status.CANCELLED
        entry.save(update_fields=["status", "updated_at"])
        messages.success(request, "Réservation annulée.")
    else:
        messages.error(request, "Action invalide.")

    return redirect("/partner/agenda/")


@login_required
def partner_analytics_page(request):
    if not _is_professional_account(request.user):
        return redirect("/devenir-partenaire/")
    denied = _require_offer_tier(
        request,
        minimum_tier="mid",
        feature_label="Analytics avancees",
        fallback_url="/partner/settings/",
    )
    if denied:
        return denied

    partner = Partner.objects.filter(owner=request.user).first()
    analytics_note = ""
    if not partner:
        partner = {
            "name": "Compte Activite Pro",
            "city": request.user.city or "Marseille",
            "id": None,
        }
        analytics_note = "Profil partenaire introuvable: affichage du mode compte actif (demonstration)."

    partner_id = partner.get("id") if isinstance(partner, dict) else partner.id
    partner_city = partner.get("city") if isinstance(partner, dict) else partner.city

    partner_events = Event.objects.filter(Q(partner_id=partner_id) | Q(city__iexact=partner_city))
    published_events = partner_events.filter(status=Event.Status.PUBLISHED)

    total_events = partner_events.count()
    active_events = published_events.count()
    upcoming_events = published_events.filter(starts_at__gte=timezone.now()).count()

    city_sorties = Sortie.objects.filter(city__iexact=partner_city)
    city_bookings = Booking.objects.filter(sortie_id__in=city_sorties.values_list("id", flat=True))
    confirmed_city_bookings = city_bookings.filter(status=Booking.Status.CONFIRMED).count()
    conversion_rate = round((confirmed_city_bookings / city_bookings.count()) * 100, 2) if city_bookings.count() else 0

    city_revenue = sum(
        p.amount
        for p in Payment.objects.filter(
            status=Payment.Status.SUCCEEDED,
            booking_id__in=city_bookings.values_list("id", flat=True),
        )
    )

    active_promotions = SponsoredEvent.objects.filter(
        city__iexact=partner_city,
        status=SponsoredEvent.Status.ACTIVE,
        ends_at__gte=timezone.now(),
    ).count()

    kpis = {
        "total_events": total_events,
        "active_events": active_events,
        "upcoming_events": upcoming_events,
        "conversion_rate": conversion_rate,
        "city_revenue": city_revenue,
        "active_promotions": active_promotions,
    }

    if not any([
        kpis["total_events"],
        kpis["active_events"],
        kpis["upcoming_events"],
        kpis["conversion_rate"],
        kpis["city_revenue"],
        kpis["active_promotions"],
    ]):
        kpis = {
            "total_events": 14,
            "active_events": 6,
            "upcoming_events": 4,
            "conversion_rate": 31.5,
            "city_revenue": 428500,
            "active_promotions": 3,
        }
        analytics_note = "Affichage en mode compte actif (exemples de demonstration)."

    events = list(published_events.order_by("starts_at")[:20])
    if not events:
        events = [
            {"title": "Karting Sunset Cup", "city": partner_city or "Marseille", "starts_at": timezone.now() + timedelta(days=1, hours=2)},
            {"title": "Laser Night Challenge", "city": partner_city or "Marseille", "starts_at": timezone.now() + timedelta(days=2, hours=1)},
            {"title": "Escape Duo Mission", "city": partner_city or "Marseille", "starts_at": timezone.now() + timedelta(days=3, hours=3)},
        ]

    public_page = _professional_public_page_payload(request.user)

    return render(request, "web/platform/partner_analytics.html", {
        "partner": partner,
        "kpis": kpis,
        "events": events,
        "analytics_note": analytics_note,
        "public_page_url": public_page["url"],
        "public_page_label": public_page["label"],
        "highlight_blocks": [
            {"label": "Panier moyen", "value": "96 EUR", "meta": "sur activites confirmees"},
            {"label": "No-show", "value": "4.2%", "meta": "en baisse de 1.1 pt"},
            {"label": "Heure forte", "value": "20:00", "meta": "pic de reservation"},
        ],
    })


@login_required
def partner_payments_page(request):
    if not _is_professional_account(request.user):
        return redirect("/devenir-partenaire/")
    rows = Payment.objects.order_by("-created_at")[:25]
    rows_data = [{"title": p.stripe_payment_intent_id, "meta": p.get_status_display()} for p in rows]
    if not rows_data:
        rows_data = _partner_demo_rows("payments")

    highlight_blocks = [
        {"label": "Encaisse", "value": "1 248 EUR", "meta": "semaine en cours"},
        {"label": "En attente", "value": "282 EUR", "meta": "captures programmees"},
        {"label": "Rembourse", "value": "45 EUR", "meta": "1 transaction"},
    ]
    public_page = _professional_public_page_payload(request.user)

    return render(request, "web/platform/dashboard_list.html", {
        "title": "Partner payments",
        "subtitle": "Paiements Stripe et statuts (compte actif)",
        "rows_data": rows_data,
        "highlight_blocks": highlight_blocks,
        "public_page_url": public_page["url"],
        "public_page_label": public_page["label"],
    })


@login_required
def partner_requests_page(request):
    if not _is_professional_account(request.user):
        return redirect("/devenir-partenaire/")
    partner = Partner.objects.filter(owner=request.user).first()
    opportunities = PartnerOpportunity.objects.order_by("-created_at")
    if partner and partner.city:
        opportunities = opportunities.filter(city__iexact=partner.city)
    rows_data = [{"title": o.title, "meta": f"{o.city} - {o.get_status_display()}"} for o in opportunities[:30]]
    if not rows_data:
        rows_data = _partner_demo_rows("requests")

    highlight_blocks = [
        {"label": "Nouvelles", "value": "4", "meta": "depuis ce matin"},
        {"label": "A valider", "value": "7", "meta": "action requise"},
        {"label": "Confirmees", "value": "11", "meta": "avec acompte recu"},
    ]
    public_page = _professional_public_page_payload(request.user)

    return render(request, "web/platform/dashboard_list.html", {
        "title": "Partner requests",
        "subtitle": "Demandes d'activites a traiter (compte actif)",
        "rows_data": rows_data,
        "highlight_blocks": highlight_blocks,
        "public_page_url": public_page["url"],
        "public_page_label": public_page["label"],
    })


@login_required
def partner_settings_page(request):
    if not _is_professional_account(request.user):
        return redirect("/devenir-partenaire/")

    if request.method == "GET" and request.GET.get("edit") != "1":
        public_page = _professional_public_page_payload(request.user)
        if public_page["url"]:
            return redirect(public_page["url"])

    partner = Partner.objects.filter(owner=request.user).first()
    public_page = _professional_public_page_payload(request.user)
    public_page_url = public_page["url"]

    if not partner:
        actions = [{"href": "/devenir-partenaire/", "label": "Creer mon profil partenaire"}]
        if public_page_url:
            actions.insert(0, {"href": public_page_url, "label": "Voir ma page publique"})

        return render(request, "web/platform/simple_page.html", {
            "title": "Partner settings",
            "subtitle": "Parametres compte partenaire",
            "description": "Profil partenaire introuvable. Cree ou rattache un profil partenaire pour gerer l'offre.",
            "items": [
                "Aucun profil partenaire detecte pour ce compte.",
                "La section et l'offre ne peuvent pas etre modifiees sans profil.",
            ],
            "actions": actions,
        })

    if request.method == "POST":
        tier = (request.POST.get("pro_offer_tier") or "").strip().lower()
        allowed_tiers = {"low", "mid", "high"}

        if tier not in allowed_tiers:
            messages.error(request, "Selection d'offre invalide.")
            return redirect("/partner/settings/")

        updates = []
        if partner.pro_offer_tier != tier:
            partner.pro_offer_tier = tier
            updates.append("pro_offer_tier")

        if updates:
            updates.append("updated_at")
            partner.save(update_fields=updates)
            messages.success(request, "Parametres d'offre mis a jour.")
        else:
            messages.info(request, "Aucun changement detecte.")

        return redirect("/partner/settings/")

    return render(request, "web/platform/partner_settings.html", {
        "partner": partner,
        "public_page_url": public_page_url,
        "offer_options": [
            {
                "value": "low",
                "label": "Offre basse",
                "meta": "Starter",
                "features": [
                    "Fonctions fondamentales",
                    "Sans analytics avancees",
                    "Sans creation premium",
                ],
            },
            {
                "value": "mid",
                "label": "Offre moyenne",
                "meta": "Pro",
                "features": [
                    "Analytics avancees",
                    "Creation d'evenements premium",
                    "Automatisations business",
                ],
            },
            {
                "value": "high",
                "label": "Offre haute",
                "meta": "Elite",
                "features": [
                    "Toutes options Pro",
                    "Scan QR avance nightlife",
                    "Priorite support et optimisation",
                ],
            },
        ],
    })


@login_required
def partner_establishment_redirect(request):
    if not _is_professional_account(request.user):
        return redirect("/devenir-partenaire/")

    public_page = _professional_public_page_payload(request.user)
    if public_page["url"]:
        return redirect(public_page["url"])

    messages.info(request, "Aucune page publique disponible pour ce compte.")
    return redirect("/partner/settings/")


@login_required
def partner_events_create_page(request):
    if not _is_professional_account(request.user):
        return redirect("/devenir-partenaire/")
    denied = _require_offer_tier(
        request,
        minimum_tier="mid",
        feature_label="Creation d'evenements premium",
        fallback_url="/partner/events/",
    )
    if denied:
        return denied

    return create_activity_request(request)


@login_required
def nightlife_dashboard(request):
    return render(request, "web/platform/simple_page.html", {
        "title": "Nightlife dashboard",
        "subtitle": "Pilotage etablissements",
        "description": "Publie tes evenements nightlife, gere la billetterie QR, suis les ventes et tes promotions.",
    })


@login_required
def nightlife_events_page(request):
    rows = Event.objects.filter(is_partner_event=True).order_by("-created_at")[:25]
    rows_data = [{"title": e.title, "meta": e.city} for e in rows]
    return render(request, "web/platform/dashboard_list.html", {
        "title": "Nightlife events",
        "subtitle": "Evenements clubs, bars, rooftops",
        "rows_data": rows_data,
    })


@login_required
def nightlife_analytics_page(request):
    if not (request.user.is_staff or request.user.is_partner):
        return redirect("/nightlife/dashboard/")
    return partner_analytics_page(request)


@login_required
def nightlife_events_create_page(request):
    if not (request.user.is_staff or request.user.is_partner):
        return redirect("/nightlife/dashboard/")
    return create_activity_request(request)


@login_required
def nightlife_tickets_page(request):
    rows = Booking.objects.filter(booking_type=Booking.BookingType.ACTIVITY).order_by("-created_at")[:25]
    rows_data = [{"title": f"Ticket #{b.id}", "meta": b.get_status_display()} for b in rows]
    return render(request, "web/platform/dashboard_list.html", {
        "title": "Nightlife tickets",
        "subtitle": "Billetterie et scans d'entree",
        "rows_data": rows_data,
    })


@login_required
def nightlife_ticket_scan_page(request):
    denied = _ensure_operator_access(request)
    if denied:
        return denied

    denied = _require_offer_tier(
        request,
        minimum_tier="high",
        feature_label="Scan QR avance",
        fallback_url="/nightlife/tickets/",
    )
    if denied:
        return denied

    result = None
    qr_token = ""
    if request.method == "POST":
        scan_key = _rate_limit_key("ticket-scan", request)
        if _is_rate_limited(scan_key, 120):
            emit_alert("tickets.scan.rate_limited", request=request, severity="warning")
            result = {
                "status": "error",
                "message": "Trop de scans en peu de temps. Merci de patienter.",
                "reason_code": "rate_limited",
            }
            latest_scans = TicketScanAudit.objects.select_related("ticket").order_by("-created_at")[:15]
            return render(request, "web/platform/ticket_scan.html", {
                "result": result,
                "qr_token": "",
                "latest_scans": latest_scans,
                "operator_city": request.user.city or "",
            }, status=429)
        _rate_limit_hit(scan_key, ttl_seconds=300)

        qr_token = (request.POST.get("qr_token") or "").strip()
        scan_source = (request.POST.get("source") or TicketScanAudit.Source.WEB).upper()
        scan_source = scan_source if scan_source in TicketScanAudit.Source.values else TicketScanAudit.Source.WEB
        ticket = Ticket.objects.filter(qr_token=qr_token).first()

        operator_city = ""
        if not request.user.is_staff:
            operator_city = request.user.city or ""
            partner = Partner.objects.filter(owner=request.user, status=Partner.Status.ACTIVE).only("city").first()
            if partner and partner.city:
                operator_city = partner.city

        if not ticket:
            failures = alert_on_threshold(
                f"tickets:scan:not_found:{request.user.id}",
                threshold=10,
                window_seconds=300,
                alert_name="tickets.scan.high_not_found_rate",
                request=request,
                severity="warning",
            )
            TicketScanAudit.objects.create(
                ticket=None,
                operator=request.user,
                scanned_token=qr_token[:80],
                outcome=TicketScanAudit.Outcome.NOT_FOUND,
                reason_code="ticket_not_found",
                source=scan_source,
                operator_city=operator_city,
            )
            emit_event("tickets.scan.not_found", request=request, failures_5m=failures)
            result = {"status": "error", "message": "Ticket introuvable.", "reason_code": "ticket_not_found"}
        elif ticket.status == Ticket.Status.CANCELLED:
            TicketScanAudit.objects.create(
                ticket=ticket,
                operator=request.user,
                scanned_token=qr_token[:80],
                outcome=TicketScanAudit.Outcome.INVALID_STATUS,
                reason_code="status_cancelled",
                source=scan_source,
                operator_city=operator_city,
            )
            result = {"status": "error", "message": "Ticket annule.", "reason_code": "status_cancelled"}
        elif ticket.status == Ticket.Status.USED:
            TicketScanAudit.objects.create(
                ticket=ticket,
                operator=request.user,
                scanned_token=qr_token[:80],
                outcome=TicketScanAudit.Outcome.INVALID_STATUS,
                reason_code="status_used",
                source=scan_source,
                operator_city=operator_city,
            )
            result = {"status": "error", "message": "Ticket deja utilise.", "reason_code": "status_used"}
        elif ticket.status != Ticket.Status.ACTIVE:
            TicketScanAudit.objects.create(
                ticket=ticket,
                operator=request.user,
                scanned_token=qr_token[:80],
                outcome=TicketScanAudit.Outcome.INVALID_STATUS,
                reason_code=f"status_{ticket.status.lower()}",
                source=scan_source,
                operator_city=operator_city,
            )
            result = {
                "status": "error",
                "message": "Ticket non valide.",
                "reason_code": f"status_{ticket.status.lower()}",
            }
        else:
            from django.utils import timezone

            target_city = ""
            ownership_allowed = True
            ownership_reason = ""
            partner = Partner.objects.filter(owner=request.user, status=Partner.Status.ACTIVE).only("id", "city").first()
            if ticket.sortie_id:
                sortie = Sortie.objects.filter(id=ticket.sortie_id).only("city", "type", "creator_id").first()
                target_city = sortie.city if sortie else ""
                if request.user.is_partner:
                    if not sortie:
                        ownership_allowed = False
                        ownership_reason = "sortie_not_found"
                    elif sortie.type != Sortie.Type.PARTENAIRE:
                        ownership_allowed = False
                        ownership_reason = "sortie_not_partner"
                    elif not sortie.creator_id:
                        ownership_allowed = False
                        ownership_reason = "sortie_without_owner"
                    elif sortie.creator_id != request.user.id:
                        ownership_allowed = False
                        ownership_reason = "sortie_owner_mismatch"
            elif ticket.event_id:
                event = Event.objects.filter(id=ticket.event_id).only("city", "partner_id").first()
                target_city = event.city if event else ""
                if request.user.is_partner:
                    if not partner:
                        ownership_allowed = False
                        ownership_reason = "inactive_partner"
                    elif not event:
                        ownership_allowed = False
                        ownership_reason = "event_not_found"
                    elif not event.partner_id:
                        ownership_allowed = False
                        ownership_reason = "event_without_partner"
                    elif event.partner_id != partner.id:
                        ownership_allowed = False
                        ownership_reason = "event_partner_mismatch"
            elif request.user.is_partner:
                ownership_allowed = False
                ownership_reason = "ticket_missing_target"

            if request.user.is_partner and not ownership_allowed:
                failures = alert_on_threshold(
                    f"tickets:scan:forbidden_scope:{request.user.id}",
                    threshold=8,
                    window_seconds=300,
                    alert_name="tickets.scan.high_forbidden_scope_rate",
                    request=request,
                    severity="warning",
                    reason=ownership_reason,
                )
                TicketScanAudit.objects.create(
                    ticket=ticket,
                    operator=request.user,
                    scanned_token=qr_token[:80],
                    outcome=TicketScanAudit.Outcome.FORBIDDEN_SCOPE,
                    reason_code=ownership_reason,
                    source=scan_source,
                    operator_city=operator_city,
                    target_city=target_city,
                )
                result = {
                    "status": "error",
                    "message": "Ticket hors perimetre operateur.",
                    "reason_code": ownership_reason,
                }
                emit_event(
                    "tickets.scan.forbidden_scope",
                    request=request,
                    reason_code=ownership_reason,
                    failures_5m=failures,
                )
                latest_scans = TicketScanAudit.objects.select_related("ticket").order_by("-created_at")[:15]
                return render(request, "web/platform/ticket_scan.html", {
                    "result": result,
                    "qr_token": qr_token,
                    "latest_scans": latest_scans,
                    "operator_city": operator_city,
                })

            ticket.status = Ticket.Status.USED
            ticket.used_at = timezone.now()
            ticket.save(update_fields=["status", "used_at", "updated_at"])

            TicketScanAudit.objects.create(
                ticket=ticket,
                operator=request.user,
                scanned_token=qr_token[:80],
                outcome=TicketScanAudit.Outcome.SUCCESS,
                reason_code="ok",
                source=scan_source,
                operator_city=operator_city,
                target_city=target_city,
            )
            emit_event("tickets.scan.success", request=request, ticket_id=ticket.id, target_city=target_city)
            result = {
                "status": "success",
                "message": f"Entree validee pour le ticket #{ticket.id}.",
                "ticket": ticket,
                "target_city": target_city,
            }

    latest_scans = TicketScanAudit.objects.select_related("ticket").order_by("-created_at")[:15]

    return render(request, "web/platform/ticket_scan.html", {
        "result": result,
        "qr_token": qr_token,
        "latest_scans": latest_scans,
        "operator_city": request.user.city or "",
    })


@login_required
def nightlife_promotions_page(request):
    if not (request.user.is_staff or request.user.is_partner):
        messages.error(request, "Acces reserve aux operateurs nightlife.")
        return redirect("/nightlife/dashboard/")

    partner = Partner.objects.filter(owner=request.user).first() if request.user.is_partner else None

    if request.method == "POST":
        event_id = request.POST.get("event_id")
        city = (request.POST.get("city") or (partner.city if partner else "")).strip()
        budget_eur = int(request.POST.get("budget_eur") or 30)
        days = int(request.POST.get("days") or 7)

        if event_id and city:
            SponsoredEvent.objects.create(
                city=city,
                event_id=int(event_id),
                budget_eur=max(budget_eur, 10),
                starts_at=timezone.now(),
                ends_at=timezone.now() + timedelta(days=max(days, 1)),
                status=SponsoredEvent.Status.ACTIVE,
            )
            messages.success(request, "Campagne promotionnelle activee.")
            return redirect("/nightlife/promotions/")
        messages.error(request, "Event et ville requis pour lancer une campagne.")

    campaigns = SponsoredEvent.objects.all().order_by("-created_at")
    if request.user.is_partner and partner:
        campaigns = campaigns.filter(city__iexact=partner.city)

    nightlife_events = Event.objects.filter(is_partner_event=True)
    if request.user.is_partner and partner:
        nightlife_events = nightlife_events.filter(Q(partner_id=partner.id) | Q(city__iexact=partner.city))

    return render(request, "web/platform/nightlife_promotions.html", {
        "partner": partner,
        "campaigns": campaigns[:40],
        "nightlife_events": nightlife_events.order_by("-created_at")[:80],
    })


def _ensure_admin_access(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        messages.error(request, "Acces reserve aux administrateurs.")
        return redirect("/connexion/?next=/admin/")
    return None


def _ensure_operator_access(request):
    if not request.user.is_authenticated:
        messages.error(request, "Connexion requise.")
        return redirect("/connexion/?next=/nightlife/tickets/scan/")
    if not (request.user.is_staff or request.user.is_partner):
        messages.error(request, "Acces reserve aux operateurs ou partenaires.")
        return redirect("/nightlife/tickets/")
    return None


def admin_dashboard(request):
    denied = _ensure_admin_access(request)
    if denied:
        return denied
    kpis = {
        "users_count": User.objects.count(),
        "active_events": Event.objects.filter(status=Event.Status.PUBLISHED).count(),
        "active_sorties": Sortie.objects.filter(status=Sortie.Status.OPEN).count(),
        "revenue_cents": sum(p.amount for p in Payment.objects.filter(status=Payment.Status.SUCCEEDED)),
        "otp_alerts_24h": get_otp_alerts_last_24h(),
    }
    return render(request, "web/platform/admin_dashboard.html", {"kpis": kpis})


def admin_users_page(request):
    denied = _ensure_admin_access(request)
    if denied:
        return denied
    rows = User.objects.order_by("-date_joined")[:50]
    rows_data = [{"title": u.email, "meta": u.city or "-"} for u in rows]
    return render(request, "web/platform/dashboard_list.html", {
        "title": "Admin users",
        "subtitle": "Gestion utilisateurs et roles",
        "rows_data": rows_data,
    })


def admin_events_page(request):
    denied = _ensure_admin_access(request)
    if denied:
        return denied
    rows = Event.objects.order_by("-created_at")[:50]
    rows_data = [{"title": e.title, "meta": e.get_status_display()} for e in rows]
    return render(request, "web/platform/dashboard_list.html", {
        "title": "Admin events",
        "subtitle": "Moderation des evenements",
        "rows_data": rows_data,
    })


def admin_partners_page(request):
    denied = _ensure_admin_access(request)
    if denied:
        return denied
    rows = Partner.objects.order_by("-created_at")[:60]
    rows_data = [{"title": p.name, "meta": f"{p.city} - {p.get_status_display()}"} for p in rows]
    return render(request, "web/platform/dashboard_list.html", {
        "title": "Admin partners",
        "subtitle": "Suivi onboarding, verification et statut des partenaires",
        "rows_data": rows_data,
    })


def admin_reports_page(request):
    denied = _ensure_admin_access(request)
    if denied:
        return denied
    if request.method == "POST":
        report_id = request.POST.get("report_id")
        action_name = (request.POST.get("action") or "").strip().lower()
        notes = (request.POST.get("notes") or "").strip()
        try:
            sla_hours = int(request.POST.get("sla_hours") or 24)
        except (TypeError, ValueError):
            sla_hours = 24
        try:
            suspension_days = int(request.POST.get("suspension_days") or 7)
        except (TypeError, ValueError):
            suspension_days = 7
        report = Report.objects.filter(id=report_id).first()

        if report:
            report.reviewed_by = request.user
            report.moderation_notes = notes
            history = list(report.decision_history or [])

            if action_name == "assign_me":
                report.assigned_moderator = request.user
                report.status = Report.Status.IN_REVIEW
                report.sla_due_at = timezone.now() + timedelta(hours=max(sla_hours, 1))
                history.append({
                    "at": timezone.now().isoformat(),
                    "actor_email": request.user.email,
                    "action": "assign_me",
                    "sla_hours": sla_hours,
                })
            elif action_name == "resolve":
                report.status = Report.Status.RESOLVED
                report.reviewed_at = timezone.now()
                report.resolution_code = Report.ResolutionCode.RESOLVED_NO_ACTION
            elif action_name == "dismiss":
                report.status = Report.Status.DISMISSED
                report.reviewed_at = timezone.now()
                report.resolution_code = Report.ResolutionCode.DISMISSED_NO_VIOLATION
            elif action_name == "ban_user" and report.target_type == Report.TargetType.USER:
                user = User.objects.filter(id=report.target_id).first()
                if user:
                    user.is_active = False
                    user.save(update_fields=["is_active"])
                report.status = Report.Status.RESOLVED
                report.reviewed_at = timezone.now()
                report.resolution_code = Report.ResolutionCode.USER_BANNED
            elif action_name == "temp_suspend_user" and report.target_type == Report.TargetType.USER:
                report.status = Report.Status.RESOLVED
                report.reviewed_at = timezone.now()
                report.resolution_code = Report.ResolutionCode.USER_TEMP_SUSPENDED
                report.suspension_ends_at = timezone.now() + timedelta(days=max(suspension_days, 1))
            elif action_name == "remove_sortie" and report.target_type == Report.TargetType.SORTIE:
                Sortie.objects.filter(id=report.target_id).update(status=Sortie.Status.CANCELLED)
                report.status = Report.Status.RESOLVED
                report.reviewed_at = timezone.now()
                report.resolution_code = Report.ResolutionCode.CONTENT_REMOVED
            elif action_name == "remove_event" and report.target_type == Report.TargetType.EVENT:
                Event.objects.filter(id=report.target_id).update(status=Event.Status.CANCELLED)
                report.status = Report.Status.RESOLVED
                report.reviewed_at = timezone.now()
                report.resolution_code = Report.ResolutionCode.CONTENT_REMOVED
            else:
                report.status = Report.Status.IN_REVIEW

            history.append({
                "at": timezone.now().isoformat(),
                "actor_email": request.user.email,
                "action": action_name,
                "notes": notes,
            })
            report.decision_history = history
            report.save(
                update_fields=[
                    "status",
                    "reviewed_by",
                    "assigned_moderator",
                    "sla_due_at",
                    "reviewed_at",
                    "resolution_code",
                    "suspension_ends_at",
                    "moderation_notes",
                    "decision_history",
                    "updated_at",
                ]
            )
            send_report_moderation_notifications(report, request.user, action_name or "review")
            messages.success(request, "Action de moderation appliquee.")

    reports = Report.objects.select_related("reporter", "reviewed_by", "assigned_moderator").order_by("-created_at")[:100]
    partner_rows = PartnerOpportunity.objects.order_by("-created_at")[:20]
    return render(request, "web/platform/admin_reports.html", {
        "reports": reports,
        "partner_rows": partner_rows,
    })


def admin_payments_page(request):
    denied = _ensure_admin_access(request)
    if denied:
        return denied
    rows = Payment.objects.order_by("-created_at")[:50]
    rows_data = [{"title": p.stripe_payment_intent_id, "meta": p.get_status_display()} for p in rows]
    return render(request, "web/platform/dashboard_list.html", {
        "title": "Admin payments",
        "subtitle": "Suivi paiements et remboursements",
        "rows_data": rows_data,
    })


def admin_ads_page(request):
    denied = _ensure_admin_access(request)
    if denied:
        return denied
    return render(request, "web/platform/simple_page.html", {
        "title": "Admin ads",
        "subtitle": "Publicite locale premium",
        "description": "Regle active: maximum 3 evenements sponsorises actifs par ville.",
        "actions": [
            {"href": "/api/v1/ads/", "label": "Voir API ads"},
        ],
    })


def admin_analytics_page(request):
    denied = _ensure_admin_access(request)
    if denied:
        return denied
    period = (request.GET.get("period") or "month").strip().lower()
    now = timezone.now()

    if period == "day":
        start = now - timedelta(days=1)
    elif period == "week":
        start = now - timedelta(days=7)
    elif period == "quarter":
        start = now - timedelta(days=90)
    else:
        period = "month"
        start = now - timedelta(days=30)

    days_count = max((now - start).days, 1)
    prev_end = start
    prev_start = prev_end - timedelta(days=days_count)

    bookings_qs = Booking.objects.filter(created_at__gte=start, created_at__lte=now)
    prev_bookings_qs = Booking.objects.filter(created_at__gte=prev_start, created_at__lt=prev_end)

    total_bookings = bookings_qs.count()
    confirmed_bookings = bookings_qs.filter(status=Booking.Status.CONFIRMED).count()
    prev_total_bookings = prev_bookings_qs.count()
    prev_confirmed_bookings = prev_bookings_qs.filter(status=Booking.Status.CONFIRMED).count()

    succeeded_payments = list(
        Payment.objects.filter(status=Payment.Status.SUCCEEDED, created_at__gte=start, created_at__lte=now)
    )
    refunded_payments = list(
        Payment.objects.filter(status=Payment.Status.REFUNDED, created_at__gte=start, created_at__lte=now)
    )
    prev_succeeded_payments = list(
        Payment.objects.filter(status=Payment.Status.SUCCEEDED, created_at__gte=prev_start, created_at__lt=prev_end)
    )

    revenue_cents = sum(p.amount for p in succeeded_payments)
    refunds_cents = sum(p.amount for p in refunded_payments)
    net_revenue_cents = revenue_cents - refunds_cents
    prev_revenue_cents = sum(p.amount for p in prev_succeeded_payments)

    booking_ids = [p.booking_id for p in succeeded_payments if p.booking_id]
    bookings_by_id = {b.id: b for b in Booking.objects.filter(id__in=booking_ids)}
    prev_booking_ids = [p.booking_id for p in prev_succeeded_payments if p.booking_id]
    prev_bookings_by_id = {b.id: b for b in Booking.objects.filter(id__in=prev_booking_ids)}

    sortie_ids = [b.sortie_id for b in bookings_by_id.values() if b.sortie_id]
    sorties_by_id = {s.id: s for s in Sortie.objects.filter(id__in=sortie_ids)}

    slot_ids = [b.restaurant_slot_id for b in bookings_by_id.values() if b.restaurant_slot_id]
    slots_by_id = {
        s.id: s
        for s in RestaurantTimeSlot.objects.select_related("venue").filter(id__in=slot_ids)
    }

    activity_ids = [b.activity_session_id for b in bookings_by_id.values() if b.activity_session_id]
    events_by_activity_id = {e.id: e for e in Event.objects.filter(id__in=activity_ids)}

    def _safe_float(value, default):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _safe_int(value, default):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _booking_source_and_city(booking, payment):
        if booking:
            if booking.booking_type == Booking.BookingType.SORTIE and booking.sortie_id:
                sortie = sorties_by_id.get(booking.sortie_id)
                if sortie:
                    return "sortie", sortie.city or "Inconnue"
            if booking.booking_type == Booking.BookingType.RESTAURANT and booking.restaurant_slot_id:
                slot = slots_by_id.get(booking.restaurant_slot_id)
                if slot and slot.venue:
                    return "restaurant", slot.venue.city_label or "Inconnue"
            if booking.booking_type == Booking.BookingType.ACTIVITY and booking.activity_session_id:
                event = events_by_activity_id.get(booking.activity_session_id)
                if event:
                    return "event", event.city or "Inconnue"
                return "activity", "Inconnue"

        metadata_city = (payment.metadata or {}).get("city") if payment else ""
        return "unknown", (metadata_city or "Inconnue")

    def _finance_rules(booking, payment):
        metadata = payment.metadata or {}
        source = booking.booking_type if booking else "UNKNOWN"

        # Baseline rules by source; override via payment.metadata for partner-level agreements.
        commission_by_source = {
            Booking.BookingType.SORTIE: 0.10,
            Booking.BookingType.RESTAURANT: 0.08,
            Booking.BookingType.ACTIVITY: 0.12,
            "UNKNOWN": 0.10,
        }
        tax_by_source = {
            Booking.BookingType.SORTIE: 0.20,
            Booking.BookingType.RESTAURANT: 0.20,
            Booking.BookingType.ACTIVITY: 0.20,
            "UNKNOWN": 0.20,
        }

        commission_rate = _safe_float(metadata.get("commission_rate"), commission_by_source.get(source, 0.10))
        processing_rate = _safe_float(metadata.get("processing_rate"), 0.014)
        processing_fixed_cents = _safe_int(metadata.get("processing_fixed_cents"), 25)
        tax_rate = _safe_float(metadata.get("tax_rate"), tax_by_source.get(source, 0.20))
        return {
            "commission_rate": max(commission_rate, 0),
            "processing_rate": max(processing_rate, 0),
            "processing_fixed_cents": max(processing_fixed_cents, 0),
            "tax_rate": max(tax_rate, 0),
        }

    commission_cents = 0
    processing_fees_cents = 0
    tax_cents = 0
    platform_net_cents = 0

    prev_commission_cents = 0
    prev_processing_fees_cents = 0
    prev_tax_cents = 0
    prev_platform_net_cents = 0

    source_totals = defaultdict(lambda: {
        "source": "",
        "bookings": 0,
        "revenue_cents": 0,
        "commission_cents": 0,
        "processing_fees_cents": 0,
        "tax_cents": 0,
        "platform_net_cents": 0,
    })

    for payment in succeeded_payments:
        booking = bookings_by_id.get(payment.booking_id)
        rules = _finance_rules(booking, payment)
        source, city = _booking_source_and_city(booking, payment)

        fee_commission = int(payment.amount * rules["commission_rate"])
        fee_processing = int(payment.amount * rules["processing_rate"]) + rules["processing_fixed_cents"]
        fee_tax = int((fee_commission + fee_processing) * rules["tax_rate"])
        fee_platform_net = max(fee_commission - fee_processing - fee_tax, 0)

        commission_cents += fee_commission
        processing_fees_cents += fee_processing
        tax_cents += fee_tax
        platform_net_cents += fee_platform_net

        city_row = source_totals[(city, source)]
        city_row["source"] = source
        city_row["bookings"] += 1
        city_row["revenue_cents"] += payment.amount
        city_row["commission_cents"] += fee_commission
        city_row["processing_fees_cents"] += fee_processing
        city_row["tax_cents"] += fee_tax
        city_row["platform_net_cents"] += fee_platform_net

    for payment in prev_succeeded_payments:
        booking = prev_bookings_by_id.get(payment.booking_id)
        rules = _finance_rules(booking, payment)
        fee_commission = int(payment.amount * rules["commission_rate"])
        fee_processing = int(payment.amount * rules["processing_rate"]) + rules["processing_fixed_cents"]
        fee_tax = int((fee_commission + fee_processing) * rules["tax_rate"])
        fee_platform_net = max(fee_commission - fee_processing - fee_tax, 0)

        prev_commission_cents += fee_commission
        prev_processing_fees_cents += fee_processing
        prev_tax_cents += fee_tax
        prev_platform_net_cents += fee_platform_net

    conversion_rate = round((confirmed_bookings / total_bookings) * 100, 2) if total_bookings else 0
    prev_conversion_rate = round((prev_confirmed_bookings / prev_total_bookings) * 100, 2) if prev_total_bookings else 0

    open_inventory = (
        Sortie.objects.filter(status=Sortie.Status.OPEN).count()
        + Event.objects.filter(status=Event.Status.PUBLISHED).count()
    )
    funnel = {
        "inventory_open": open_inventory,
        "bookings_created": total_bookings,
        "bookings_confirmed": confirmed_bookings,
        "payments_succeeded": len(succeeded_payments),
    }

    capacity_sorties = Sortie.objects.filter(max_participants__isnull=False).annotate(pc=Count("participants"))
    total_capacity = sum(s.max_participants or 0 for s in capacity_sorties)
    total_filled = sum(min(s.pc, s.max_participants or 0) for s in capacity_sorties)
    fill_rate = round((total_filled / total_capacity) * 100, 2) if total_capacity else 0

    cities = {}
    for city_data in Sortie.objects.values("city").annotate(count=Count("id")):
        city = city_data["city"] or "Inconnue"
        cities.setdefault(
            city,
            {
                "sorties": 0,
                "events": 0,
                "bookings": 0,
                "revenue_cents": 0,
                "commission_cents": 0,
                "processing_fees_cents": 0,
                "tax_cents": 0,
                "platform_net_cents": 0,
            },
        )
        cities[city]["sorties"] = city_data["count"]

    for city_data in Event.objects.values("city").annotate(count=Count("id")):
        city = city_data["city"] or "Inconnue"
        cities.setdefault(
            city,
            {
                "sorties": 0,
                "events": 0,
                "bookings": 0,
                "revenue_cents": 0,
                "commission_cents": 0,
                "processing_fees_cents": 0,
                "tax_cents": 0,
                "platform_net_cents": 0,
            },
        )
        cities[city]["events"] = city_data["count"]

    for booking in bookings_by_id.values():
        source, city = _booking_source_and_city(booking, None)
        cities.setdefault(
            city,
            {
                "sorties": 0,
                "events": 0,
                "bookings": 0,
                "revenue_cents": 0,
                "commission_cents": 0,
                "processing_fees_cents": 0,
                "tax_cents": 0,
                "platform_net_cents": 0,
            },
        )
        cities[city]["bookings"] += 1

    for payment in succeeded_payments:
        booking = bookings_by_id.get(payment.booking_id)
        rules = _finance_rules(booking, payment)
        _, city = _booking_source_and_city(booking, payment)
        fee_commission = int(payment.amount * rules["commission_rate"])
        fee_processing = int(payment.amount * rules["processing_rate"]) + rules["processing_fixed_cents"]
        fee_tax = int((fee_commission + fee_processing) * rules["tax_rate"])
        fee_platform_net = max(fee_commission - fee_processing - fee_tax, 0)

        cities.setdefault(
            city,
            {
                "sorties": 0,
                "events": 0,
                "bookings": 0,
                "revenue_cents": 0,
                "commission_cents": 0,
                "processing_fees_cents": 0,
                "tax_cents": 0,
                "platform_net_cents": 0,
            },
        )
        cities[city]["revenue_cents"] += payment.amount
        cities[city]["commission_cents"] += fee_commission
        cities[city]["processing_fees_cents"] += fee_processing
        cities[city]["tax_cents"] += fee_tax
        cities[city]["platform_net_cents"] += fee_platform_net

    city_rows = [
        {
            "city": city,
            "sorties": data["sorties"],
            "events": data["events"],
            "bookings": data["bookings"],
            "revenue_cents": data["revenue_cents"],
            "commission_cents": data["commission_cents"],
            "processing_fees_cents": data["processing_fees_cents"],
            "tax_cents": data["tax_cents"],
            "platform_net_cents": data["platform_net_cents"],
        }
        for city, data in cities.items()
    ]
    city_rows.sort(key=lambda row: (row["platform_net_cents"], row["revenue_cents"], row["bookings"]), reverse=True)

    source_rows = []
    for (city, source), data in source_totals.items():
        source_rows.append(
            {
                "city": city,
                "source": source,
                "bookings": data["bookings"],
                "revenue_cents": data["revenue_cents"],
                "commission_cents": data["commission_cents"],
                "processing_fees_cents": data["processing_fees_cents"],
                "tax_cents": data["tax_cents"],
                "platform_net_cents": data["platform_net_cents"],
            }
        )
    source_rows.sort(key=lambda row: (row["platform_net_cents"], row["revenue_cents"]), reverse=True)

    if (request.GET.get("export") or "").lower() == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="analytics_{period}.csv"'
        response.write(
            "city,sorties,events,bookings,revenue_cents,commission_cents,processing_fees_cents,tax_cents,platform_net_cents\n"
        )
        for row in city_rows:
            response.write(
                f"{row['city']},{row['sorties']},{row['events']},{row['bookings']},{row['revenue_cents']},"
                f"{row['commission_cents']},{row['processing_fees_cents']},{row['tax_cents']},{row['platform_net_cents']}\n"
            )
        return response

    mrr_projection_cents = int((net_revenue_cents / days_count) * 30)

    fee_take_rate = round((commission_cents / revenue_cents) * 100, 2) if revenue_cents else 0
    platform_margin_rate = round((platform_net_cents / revenue_cents) * 100, 2) if revenue_cents else 0
    prev_platform_margin_rate = round((prev_platform_net_cents / prev_revenue_cents) * 100, 2) if prev_revenue_cents else 0

    return render(request, "web/platform/admin_analytics.html", {
        "period": period,
        "kpis": {
            "total_bookings": total_bookings,
            "confirmed_bookings": confirmed_bookings,
            "conversion_rate": conversion_rate,
            "revenue_cents": revenue_cents,
            "refunds_cents": refunds_cents,
            "net_revenue_cents": net_revenue_cents,
            "commission_cents": commission_cents,
            "processing_fees_cents": processing_fees_cents,
            "tax_cents": tax_cents,
            "platform_net_cents": platform_net_cents,
            "fill_rate": fill_rate,
            "mrr_projection_cents": mrr_projection_cents,
            "fee_take_rate": fee_take_rate,
            "platform_margin_rate": platform_margin_rate,
            "prev_revenue_cents": prev_revenue_cents,
            "prev_conversion_rate": prev_conversion_rate,
            "prev_commission_cents": prev_commission_cents,
            "prev_processing_fees_cents": prev_processing_fees_cents,
            "prev_tax_cents": prev_tax_cents,
            "prev_platform_net_cents": prev_platform_net_cents,
            "prev_platform_margin_rate": prev_platform_margin_rate,
        },
        "funnel": funnel,
        "city_rows": city_rows[:20],
        "source_rows": source_rows[:20],
    })


# ──────────────────────────────────────────────────────────────────────────────
# Legal / static pages
# ──────────────────────────────────────────────────────────────────────────────

_LEGAL_PAGES = {
    "cgu": (
        "Conditions Générales d'Utilisation",
        "<p><strong>Derniere mise a jour:</strong> 16/05/2026</p>"
        "<h3>1. Objet</h3>"
        "<p>Les presentes Conditions Generales d'Utilisation encadrent l'utilisation de la plateforme Mooviogo.</p>"
        "<p>Mooviogo permet l'organisation de sorties entre utilisateurs, la reservation d'activites partenaires, la publication d'evenements nightlife, l'achat de billets et l'acces a des fonctionnalites sociales et communautaires.</p>"
        "<h3>2. Acceptation des CGU</h3>"
        "<p>Toute inscription ou utilisation de la plateforme implique l'acceptation pleine et entiere des presentes CGU.</p>"
        "<h3>3. Conditions d'acces</h3>"
        "<p>L'acces a la plateforme est reserve exclusivement aux personnes majeures agees de 18 ans minimum.</p>"
        "<h3>4. Creation de compte</h3>"
        "<p>L'utilisateur s'engage a fournir des informations exactes, completes et a jour. Mooviogo se reserve le droit de suspendre ou supprimer tout compte contenant des informations fausses ou frauduleuses.</p>"
        "<h3>5. Utilisation autorisee</h3>"
        "<p>Sont strictement interdits: harcelement, spam, fraude, usurpation d'identite, contenus illicites, contenus haineux, activites illegales et contournement des systemes de paiement.</p>"
        "<h3>6. Paiements et remboursements</h3>"
        "<p>Les paiements sont traites via Stripe. Conformement a l'article L221-28 du Code de la consommation, les prestations de loisirs fournies a une date determinee ne beneficient pas du droit de retractation.</p>"
        "<h3>7. Suspension et cloture</h3>"
        "<p>Mooviogo peut suspendre ou fermer un compte en cas de fraude, non-respect des CGU, comportement dangereux ou obligation legale.</p>"
        "<h3>8. Responsabilite</h3>"
        "<p>Mooviogo agit comme intermediaire technique. Les organisateurs, partenaires et etablissements restent responsables des prestations et evenements proposes.</p>"
        "<h3>9. Droit applicable</h3>"
        "<p>Les presentes CGU sont soumises au droit francais. Tout litige releve de la competence des juridictions francaises competentes.</p>",
    ),
    "confidentialite": (
        "Politique de Confidentialité",
        "<p><strong>Derniere mise a jour:</strong> 16/05/2026</p>"
        "<h3>1. Donnees collectees</h3>"
        "<p>Nous collectons notamment: nom, prenom, email, telephone, date de naissance, ville, donnees de connexion, donnees de paiement, historique de participation et preferences utilisateur.</p>"
        "<h3>2. Finalites</h3>"
        "<p>Les donnees sont traitees pour l'execution des services, la securite, la prevention de la fraude, l'amelioration du produit, la relation client et les obligations legales.</p>"
        "<h3>3. Bases legales</h3>"
        "<p>Execution contractuelle, interet legitime (securite, lutte anti-abus), consentement lorsque requis, et respect des obligations legales.</p>"
        "<h3>4. Destinataires</h3>"
        "<p>Acces limite aux equipes habilitees, partenaires operationnels, prestataires techniques et prestataires de paiement (notamment Stripe et OVHcloud) selon le principe de minimisation.</p>"
        "<h3>5. Duree de conservation</h3>"
        "<p>Les donnees sont conservees pendant la duree necessaire au service puis archivees ou supprimees selon les obligations applicables.</p>"
        "<h3>6. Vos droits</h3>"
        "<p>Vous pouvez demander acces, rectification, opposition, limitation, suppression et portabilite, ecrire a <a href='mailto:contact@mooviogo.fr' class='text-brand'>contact@mooviogo.fr</a>.</p>"
        "<h3>7. Securite</h3>"
        "<p>Nous appliquons des mesures techniques et organisationnelles proportionnees: controle d'acces, journalisation, supervision, limitation des tentatives abusives.</p>",
    ),
    "mentions-legales": (
        "Mentions Légales",
        "<p><strong>Editeur:</strong> OUTLY, SAS au capital social de 1 000 EUR, siege social 82 RT de Montrigond, 73700 Bourg-Saint-Maurice, France.</p>"
        "<p><strong>Contact:</strong> <a href='mailto:contact@mooviogo.fr' class='text-brand'>contact@mooviogo.fr</a></p>"
        "<p><strong>Directeur de publication:</strong> Anthony Asole.</p>"
        "<p><strong>Responsable publication:</strong> Anthony Asole.</p>"
        "<p><strong>Hebergement:</strong> OVHcloud - OVH SAS, 2 rue Kellermann, 59100 Roubaix, France. Telephone: 09 72 10 10 07. Site: <a href='https://www.ovhcloud.com/fr/' target='_blank' rel='noreferrer' class='text-brand'>https://www.ovhcloud.com/fr/</a>.</p>"
        "<p><strong>Propriete intellectuelle:</strong> les contenus, marques, logos et elements graphiques de Mooviogo sont proteges. Toute reproduction non autorisee est interdite.</p>",
    ),
    "cookies": (
        "Politique de Cookies",
        "<p><strong>Derniere mise a jour:</strong> 16/05/2026</p>"
        "<h3>1. Cookies techniques (obligatoires)</h3>"
        "<p>Utilises pour la connexion, la securite des sessions, la prevention d'abus et le bon fonctionnement du site.</p>"
        "<h3>2. Cookies de mesure</h3>"
        "<p>Utilises pour analyser les usages, prioriser les ameliorations produit et suivre la stabilite du service.</p>"
        "<h3>3. Gestion de vos preferences</h3>"
        "<p>Vous pouvez configurer votre navigateur pour limiter certains cookies. Le blocage des cookies techniques peut degrader des fonctions essentielles. Les cookies sont conserves pour une duree maximale de 13 mois.</p>",
    ),
    "cgv-partenaires": (
        "CGV Partenaires",
        "<p><strong>Derniere mise a jour:</strong> 16/05/2026</p>"
        "<h3>1. Objet</h3>"
        "<p>Les presentes CGV encadrent la publication d'offres partenaires sur Mooviogo et la gestion des reservations associees.</p>"
        "<h3>2. Obligations du partenaire</h3>"
        "<p>Le partenaire garantit l'exactitude des offres, l'honoration des reservations confirmees, la conformite reglementaire et la qualite du service annonce.</p>"
        "<h3>3. Tarification et commissions</h3>"
        "<p>Les conditions financieres applicables (commission, frais de traitement, taxes) sont celles prevues contractuellement et/ou dans les regles de facturation en vigueur.</p>"
        "<h3>4. Annulations et incidents</h3>"
        "<p>En cas d'indisponibilite ou incident, le partenaire doit informer sans delai et proposer une solution conforme a la politique d'annulation/remboursement.</p>"
        "<h3>5. Suspension</h3>"
        "<p>Mooviogo peut suspendre un compte partenaire en cas de manquements repetes, fraude, non-conformite ou risque pour les utilisateurs.</p>",
    ),
    "annulation-remboursement": (
        "Politique d'annulation et remboursement",
        "<p><strong>Derniere mise a jour:</strong> 16/05/2026</p>"
        "<h3>Principe general</h3>"
        "<p>Conformement a l'article L221-28 du Code de la consommation, les prestations de loisirs fournies a une date determinee ne beneficient pas du droit de retractation.</p>"
        "<h3>Remboursements possibles</h3>"
        "<p>Les remboursements peuvent etre accordes uniquement dans les cas suivants: annulation de l'evenement, impossibilite technique, erreur de paiement, impossibilite de fournir la prestation.</p>"
        "<h3>Annulation utilisateur</h3>"
        "<p>Les partenaires peuvent appliquer leurs propres conditions de remboursement. Ces conditions sont affichees avant validation du paiement.</p>"
        "<h3>Delais</h3>"
        "<p>Les remboursements valides peuvent prendre entre 5 et 10 jours ouvres selon les etablissements bancaires.</p>"
        "<h3>Litiges</h3>"
        "<p>En cas de litige, l'utilisateur peut contacter <a href='mailto:contact@mooviogo.fr' class='text-brand'>contact@mooviogo.fr</a>.</p>",
    ),
    "a-propos": (
        "À propos de Mooviogo",
        "<p>Mooviogo facilite la rencontre entre utilisateurs, organisateurs et partenaires autour d'experiences locales: sorties, activites, evenements et restauration.</p>"
        "<p>Notre mission est de proposer une plateforme fiable, securisee et transparente, avec des parcours de reservation fluides et des outils de moderation actifs.</p>",
    ),
    "contact": (
        "Contact",
        "<p>Pour toute question (support, donnees personnelles, moderation, partenariats): <a href='mailto:contact@mooviogo.fr' class='text-brand'>contact@mooviogo.fr</a></p>"
        "<p>Merci d'indiquer votre identifiant de compte et la reference concernee pour un traitement plus rapide.</p>",
    ),
    "faq": (
        "FAQ",
        "<p><strong>Comment rejoindre une sortie ?</strong> Creez un compte, ouvrez la fiche de la sortie puis cliquez sur rejoindre/reserver.</p>"
        "<p><strong>Comment payer ?</strong> Les paiements sont traites via une infrastructure securisee. Le montant est affiche avant confirmation.</p>"
        "<p><strong>Comment annuler ?</strong> Consultez les regles d'annulation de l'offre puis initiez la demande depuis votre espace utilisateur.</p>"
        "<p><strong>Comment signaler un abus ?</strong> Utilisez le module de signalement. Les cas sont traites par moderation avec historique d'actions.</p>"
        "<p><strong>Comment exercer mes droits RGPD ?</strong> Envoyez votre demande a <a href='mailto:contact@mooviogo.fr' class='text-brand'>contact@mooviogo.fr</a>.</p>",
    ),
}


def legal_page(request, slug):
    data = _LEGAL_PAGES.get(slug)
    if not data:
        from django.http import Http404
        raise Http404
    title, content = data
    return render(request, "web/legal/page.html", {"page_title": title, "content": content})


def robots_txt(request):
    sitemap_url = request.build_absolute_uri("/sitemap.xml")
    lines = [
        "User-agent: *",
        "Allow: /",
        f"Sitemap: {sitemap_url}",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def sitemap_xml(request):
    static_paths = [
        "/",
        "/explore/",
        "/nightlife/",
        "/activities/",
        "/search/",
        "/pricing/",
        "/sorties/",
        "/restaurants/",
        "/evenements/",
        "/villes/",
        "/partenaires/",
        "/cgu/",
        "/confidentialite/",
        "/mentions-legales/",
        "/cookies/",
        "/faq/",
        "/a-propos/",
        "/contact/",
    ]

    urls = []
    for path in static_paths:
        urls.append((request.build_absolute_uri(path), None, "weekly", "0.7"))

    for sortie in Sortie.objects.filter(status=Sortie.Status.OPEN).only("id", "updated_at")[:5000]:
        urls.append((request.build_absolute_uri(f"/sorties/{sortie.id}/"), sortie.updated_at, "daily", "0.8"))

    for event in Event.objects.filter(status=Event.Status.PUBLISHED).only("slug", "updated_at")[:5000]:
        urls.append((request.build_absolute_uri(f"/evenements/{event.slug}/"), event.updated_at, "daily", "0.8"))

    for venue in RestaurantVenue.objects.filter(is_active=True).only("city_slug", "slug", "updated_at")[:5000]:
        urls.append((request.build_absolute_uri(f"/restaurants/{venue.city_slug}/{venue.slug}/"), venue.updated_at, "weekly", "0.75"))

    for partner in Partner.objects.filter(status=Partner.Status.ACTIVE).only("updated_at")[:5000]:
        # Partners currently have a list page but no slug detail route.
        urls.append((request.build_absolute_uri("/partenaires/"), partner.updated_at, "weekly", "0.6"))

    for city in (
        Sortie.objects.filter(status=Sortie.Status.OPEN)
        .values_list("city", flat=True)
        .distinct()[:1000]
    ):
        city_slug = (city or "").lower().replace(" ", "-").strip("-")
        if city_slug:
            urls.append((request.build_absolute_uri(f"/ville/{city_slug}/"), None, "weekly", "0.65"))

    parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lastmod, changefreq, priority in urls:
        parts.append("<url>")
        parts.append(f"<loc>{xml_escape(loc)}</loc>")
        if lastmod:
            parts.append(f"<lastmod>{lastmod.date().isoformat()}</lastmod>")
        parts.append(f"<changefreq>{changefreq}</changefreq>")
        parts.append(f"<priority>{priority}</priority>")
        parts.append("</url>")
    parts.append("</urlset>")

    return HttpResponse("".join(parts), content_type="application/xml")


def api_docs_page(request):
    return render(request, "web/platform/api_docs.html", {"schema_url": "/api/schema/"})
