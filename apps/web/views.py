from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.bookings.models import Booking
from apps.events.models import Event
from apps.partners.models import Partner
from apps.restaurants.models import RestaurantTimeSlot, RestaurantVenue
from apps.sorties.models import Sortie, SortieParticipant

User = get_user_model()


# ──────────────────────────────────────────────────────────────────────────────
# Home
# ──────────────────────────────────────────────────────────────────────────────

def home(request):
    sorties = Sortie.objects.filter(status=Sortie.Status.OPEN).order_by("-created_at")[:12]
    restaurants = RestaurantVenue.objects.filter(is_active=True).order_by("name")[:6]

    cities_qs = (
        Sortie.objects.filter(status=Sortie.Status.OPEN)
        .values("city")
        .annotate(count=Count("id"))
        .order_by("-count")[:12]
    )
    cities = [{"name": c["city"], "slug": c["city"].lower().replace(" ", "-"), "sortie_count": c["count"]} for c in cities_qs]

    return render(request, "web/home.html", {
        "sorties": sorties,
        "restaurants": restaurants,
        "cities": cities,
    })


# ──────────────────────────────────────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
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
        password = request.POST.get("password", "")
        password2 = request.POST.get("password2", "")
        if password != password2:
            error = "Les mots de passe ne correspondent pas."
        elif User.objects.filter(username=username).exists():
            error = "Ce nom d'utilisateur est déjà pris."
        elif User.objects.filter(email=email).exists():
            error = "Cet email est déjà utilisé."
        elif len(password) < 8:
            error = "Le mot de passe doit contenir au moins 8 caractères."
        else:
            user = User.objects.create_user(username=username, email=email, password=password)
            login(request, user)
            return redirect(request.GET.get("next") or "/")
    return render(request, "web/auth/signup.html", {"error": error})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("/")


# ──────────────────────────────────────────────────────────────────────────────
# Sorties
# ──────────────────────────────────────────────────────────────────────────────

def sorties_list(request):
    qs = Sortie.objects.all().order_by("-created_at")
    q = request.GET.get("q", "")
    city = request.GET.get("city", "")
    type_ = request.GET.get("type", "")
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if city:
        qs = qs.filter(city__icontains=city)
    if type_:
        qs = qs.filter(type=type_)
    paginator = Paginator(qs, 18)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "web/sorties/list.html", {
        "sorties": page_obj,
        "page_obj": page_obj,
        "is_paginated": paginator.num_pages > 1,
    })


def sortie_detail(request, pk):
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
    errors = {}
    form_data = {}
    if request.method == "POST":
        form_data = request.POST
        title = request.POST.get("title", "").strip()
        city = request.POST.get("city", "").strip()
        if not title:
            errors["title"] = "Le titre est requis."
        if not city:
            errors["city"] = "La ville est requise."
        if not errors:
            import re
            slug = re.sub(r"[^\w-]", "-", title.lower())[:80]
            sortie = Sortie.objects.create(
                title=title,
                slug=slug,
                description=request.POST.get("description", ""),
                city=city,
                type=request.POST.get("type", Sortie.Type.COMMUNAUTAIRE),
                is_free=bool(request.POST.get("is_free")),
                price=float(request.POST.get("price") or 0),
                max_participants=request.POST.get("max_participants") or None,
                creator=request.user,
            )
            messages.success(request, "Sortie créée avec succès !")
            return redirect(f"/sorties/{sortie.pk}/")
    return render(request, "web/sorties/create.html", {"form": type("F", (), form_data)(), "errors": errors})


@login_required
@require_POST
def sortie_join(request, pk):
    sortie = get_object_or_404(Sortie, pk=pk)
    if sortie.status == Sortie.Status.OPEN:
        SortieParticipant.objects.get_or_create(sortie=sortie, user=request.user)
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
    qs = RestaurantVenue.objects.filter(is_active=True)
    q = request.GET.get("q", "")
    city = request.GET.get("city", "")
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
    if city:
        qs = qs.filter(city__icontains=city)
    paginator = Paginator(qs.order_by("name"), 18)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "web/restaurants/list.html", {"venues": page_obj, "page_obj": page_obj, "is_paginated": paginator.num_pages > 1})


def restaurant_detail(request, city_slug, slug):
    venue = get_object_or_404(RestaurantVenue, city_slug=city_slug, slug=slug)
    from django.utils import timezone
    today = timezone.now().date()
    slots = RestaurantTimeSlot.objects.filter(venue=venue, date__gte=today).order_by("date", "time")[:20]
    return render(request, "web/restaurants/detail.html", {"venue": venue, "slots": slots})


@login_required
@require_POST
def restaurant_book(request, city_slug, slug):
    venue = get_object_or_404(RestaurantVenue, city_slug=city_slug, slug=slug)
    slot_id = request.POST.get("slot_id")
    slot = get_object_or_404(RestaurantTimeSlot, pk=slot_id, venue=venue)
    if slot.confirmed_count < slot.capacity:
        Booking.objects.create(
            user=request.user,
            restaurant_slot_id=slot.id,
            status=Booking.Status.PENDING,
        )
        slot.confirmed_count += 1
        slot.save(update_fields=["confirmed_count"])
        messages.success(request, "Réservation confirmée !")
    else:
        messages.error(request, "Ce créneau est complet.")
    return redirect(f"/restaurants/{city_slug}/{slug}/")


# ──────────────────────────────────────────────────────────────────────────────
# Events
# ──────────────────────────────────────────────────────────────────────────────

def evenements_list(request):
    events = Event.objects.filter(status=Event.Status.PUBLISHED).order_by("starts_at")
    return render(request, "web/evenements/list.html", {"events": events})


def evenement_detail(request, slug):
    event = get_object_or_404(Event, slug=slug, status=Event.Status.PUBLISHED)
    return render(request, "web/evenements/detail.html", {"event": event})


# ──────────────────────────────────────────────────────────────────────────────
# Villes
# ──────────────────────────────────────────────────────────────────────────────

def villes_list(request):
    cities_qs = (
        Sortie.objects.filter(status=Sortie.Status.OPEN)
        .values("city")
        .annotate(sortie_count=Count("id"))
        .order_by("-sortie_count")
    )
    cities = [{"name": c["city"], "slug": c["city"].lower().replace(" ", "-"), "sortie_count": c["sortie_count"]} for c in cities_qs]
    return render(request, "web/villes/list.html", {"cities": cities})


def ville_detail(request, city_slug):
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
    partners = Partner.objects.filter(status=Partner.Status.ACTIVE).select_related("owner")
    return render(request, "web/partenaires/list.html", {"partners": partners})


def devenir_partenaire(request):
    return render(request, "web/devenir_partenaire.html")


# ──────────────────────────────────────────────────────────────────────────────
# Profil
# ──────────────────────────────────────────────────────────────────────────────

@login_required
def profil(request):
    my_sorties = Sortie.objects.filter(creator=request.user).order_by("-created_at")[:5]
    return render(request, "web/profil/profil.html", {"my_sorties": my_sorties})


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
    if not request.user.is_partner:
        messages.error(request, "Accès réservé aux partenaires.")
        return redirect("/devenir-partenaire/")
    return render(request, "web/partenaire/dashboard.html")


# ──────────────────────────────────────────────────────────────────────────────
# Legal / static pages
# ──────────────────────────────────────────────────────────────────────────────

_LEGAL_PAGES = {
    "cgu": ("Conditions Générales d'Utilisation", "<p>Les CGU de Mooviogo seront publiées prochainement.</p>"),
    "confidentialite": ("Politique de Confidentialité", "<p>Notre politique de confidentialité sera publiée prochainement.</p>"),
    "mentions-legales": ("Mentions Légales", "<p>Les mentions légales de Mooviogo seront publiées prochainement.</p>"),
    "cookies": ("Politique de Cookies", "<p>Notre politique de cookies sera publiée prochainement.</p>"),
    "cgv-partenaires": ("CGV Partenaires", "<p>Les CGV partenaires seront publiées prochainement.</p>"),
    "annulation-remboursement": ("Politique d'annulation et remboursement", "<p>Notre politique d'annulation sera publiée prochainement.</p>"),
    "a-propos": ("À propos de Mooviogo", "<p>Mooviogo est une plateforme qui connecte les gens autour de sorties et de réservations de restaurants.</p>"),
    "contact": ("Contact", "<p>Pour nous contacter : <a href='mailto:hello@mooviogo.com' class='text-brand'>hello@mooviogo.com</a></p>"),
    "faq": ("FAQ", "<p>Les questions fréquemment posées seront publiées prochainement.</p>"),
}


def legal_page(request, slug):
    data = _LEGAL_PAGES.get(slug)
    if not data:
        from django.http import Http404
        raise Http404
    title, content = data
    return render(request, "web/legal/page.html", {"page_title": title, "content": content})
