from collections import defaultdict
import secrets

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.partners.models import Partner
from apps.restaurants.models import RestaurantVenue

User = get_user_model()


RESTAURANT_CATEGORY_HINTS = {
    "restaurant",
    "restauration",
    "food",
    "bistro",
    "brasserie",
    "cafe",
}


class Command(BaseCommand):
    help = "Assigne automatiquement un proprietaire aux restaurants et regle le mode de reservation."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simule l'attribution sans ecrire en base.",
        )
        parser.add_argument(
            "--set-mode",
            choices=["keep", "auto", "manual"],
            default="keep",
            help="Definit le mode de reservation pour les restaurants traites.",
        )
        parser.add_argument(
            "--include-assigned",
            action="store_true",
            help="Traite aussi les restaurants deja attribues.",
        )
        parser.add_argument(
            "--city",
            default="",
            help="Filtre les restaurants par ville (city_label ou city_slug).",
        )
        parser.add_argument(
            "--create-owner-users",
            action="store_true",
            help="Cree un compte owner automatique quand aucun partenaire owner n'est disponible.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        set_mode = options["set_mode"]
        include_assigned = options["include_assigned"]
        city_filter = (options["city"] or "").strip().lower()
        create_owner_users = options["create_owner_users"]

        venues_qs = RestaurantVenue.objects.filter(is_active=True).order_by("city_slug", "name")
        if city_filter:
            venues_qs = venues_qs.filter(city_label__icontains=city_filter) | venues_qs.filter(city_slug__icontains=city_filter)
        if not include_assigned:
            venues_qs = venues_qs.filter(owner__isnull=True)

        venues = list(venues_qs)
        if not venues:
            self.stdout.write(self.style.WARNING("Aucun restaurant a traiter."))
            return

        partners = list(
            Partner.objects.filter(
                status=Partner.Status.ACTIVE,
                is_verified=True,
                owner__isnull=False,
            )
            .select_related("owner")
            .order_by("name")
        )
        if not partners and not create_owner_users:
            self.stdout.write(self.style.WARNING("Aucun partenaire actif/verifie avec owner n'a ete trouve."))
            return

        partners_by_city = defaultdict(list)
        for p in partners:
            partners_by_city[slugify(p.city or "")].append(p)

        assigned_count_by_owner = defaultdict(int)
        assigned_now = 0
        mode_updated = 0
        skipped = 0

        self.stdout.write(
            f"Restaurants a traiter: {len(venues)} | Partenaires eligibles: {len(partners)} | dry_run={dry_run}"
        )

        @transaction.atomic
        def _process():
            nonlocal assigned_now, mode_updated, skipped
            for venue in venues:
                city_key = slugify(venue.city_label or venue.city_slug or "")
                candidates = partners_by_city.get(city_key, [])

                selected_partner = self._choose_partner_for_venue(venue, candidates, assigned_count_by_owner)
                selected_owner = selected_partner.owner if selected_partner else None
                if not selected_owner and create_owner_users:
                    selected_owner = self._get_or_create_owner_user(venue, dry_run=dry_run)

                if not selected_owner:
                    skipped += 1
                    self.stdout.write(self.style.WARNING(f"- SKIP {venue.name}: aucun owner disponible"))
                    continue

                update_fields = []
                if venue.owner_id != selected_owner.id:
                    venue.owner = selected_owner
                    update_fields.append("owner")
                    assigned_count_by_owner[selected_owner.id] += 1
                    assigned_now += 1

                if set_mode in {"auto", "manual"}:
                    target_mode = (
                        RestaurantVenue.ReservationMode.AUTO
                        if set_mode == "auto"
                        else RestaurantVenue.ReservationMode.MANUAL
                    )
                    if venue.reservation_mode != target_mode:
                        venue.reservation_mode = target_mode
                        update_fields.append("reservation_mode")
                        mode_updated += 1

                if update_fields and not dry_run:
                    venue.save(update_fields=update_fields)

                mode_label = venue.get_reservation_mode_display()
                owner_label = selected_owner.email
                self.stdout.write(
                    self.style.SUCCESS(
                        f"- OK {venue.name} -> owner={owner_label} | mode={mode_label}"
                    )
                )

            if dry_run:
                transaction.set_rollback(True)

        _process()

        self.stdout.write(
            self.style.SUCCESS(
                f"Termine. owners_assignes={assigned_now}, modes_maj={mode_updated}, ignores={skipped}, dry_run={dry_run}"
            )
        )

    def _choose_partner_for_venue(self, venue, candidates, assigned_count_by_owner):
        if not candidates:
            return None

        venue_name = (venue.name or "").lower()

        def _score(partner):
            score = 0
            partner_name = (partner.name or "").lower()
            partner_category = (partner.category or "").lower()

            if partner_name and partner_name == venue_name:
                score += 100
            elif partner_name and (partner_name in venue_name or venue_name in partner_name):
                score += 35

            if any(hint in partner_category for hint in RESTAURANT_CATEGORY_HINTS):
                score += 20

            # Keep distribution balanced between owners in same city.
            load_penalty = assigned_count_by_owner.get(partner.owner_id, 0)
            score -= load_penalty
            return score

        return max(candidates, key=_score)

    def _get_or_create_owner_user(self, venue, dry_run=False):
        base_slug = slugify(venue.slug or venue.name or "restaurant")
        if not base_slug:
            base_slug = f"restaurant-{venue.id}"

        local_part = f"owner-{base_slug}"[:48]
        email = f"{local_part}@mooviogo.local"
        username = local_part.replace("-", "_")[:150]

        existing = User.objects.filter(email=email).first()
        if existing:
            if not existing.is_partner or not existing.is_verified:
                existing.is_partner = True
                existing.is_verified = True
                if not existing.city:
                    existing.city = venue.city_label or venue.city_slug
                if not dry_run:
                    existing.save(update_fields=["is_partner", "is_verified", "city", "updated_at"])
            return existing

        if dry_run:
            shadow_user = User(email=email, username=username)
            shadow_user.id = -1
            return shadow_user

        user = User.objects.create_user(
            email=email,
            username=username,
            password=secrets.token_urlsafe(16),
            is_partner=True,
            is_verified=True,
            city=venue.city_label or venue.city_slug,
            first_name="Owner",
            last_name=venue.name[:120],
            display_name=f"Owner {venue.name}"[:80],
        )
        return user
