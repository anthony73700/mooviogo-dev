from django.urls import path

from . import views

urlpatterns = [
    # Home
    path("", views.home, name="home"),
    path("explore/", views.explore, name="explore"),
    path("feed/", views.feed_page, name="feed"),
    path("events/", views.events_alias, name="events-en"),
    path("nightlife/", views.nightlife, name="nightlife"),
    path("activities/", views.activities, name="activities"),
    path("search/", views.search_page, name="search"),
    path("pricing/", views.pricing_page, name="pricing"),
    path("robots.txt", views.robots_txt, name="robots-txt"),
    path("sitemap.xml", views.sitemap_xml, name="sitemap-xml"),

    # Auth
    path("connexion/", views.login_view, name="login"),
    path("inscription/", views.signup_view, name="signup"),
    path("inscription/request-otp/", views.signup_request_otp_view, name="signup-request-otp"),
    path("register/", views.signup_view, name="register"),
    path("login/", views.login_view, name="login-en"),
    path("forgot-password/", views.forgot_password_view, name="forgot-password"),
    path("reset-password/<uidb64>/<token>/", views.reset_password_confirm_view, name="reset-password-confirm"),
    path("deconnexion/", views.logout_view, name="logout"),

    # Sorties
    path("sorties/", views.sorties_list, name="sorties-list"),
    path("sorties/creer/", views.sortie_create, name="sortie-create"),
    path("create/free-event/", views.create_free_event, name="create-free-event"),
    path("create/activity-request/", views.create_activity_request, name="create-activity-request"),
    path("sorties/<int:pk>/", views.sortie_detail, name="sortie-detail"),
    path("sorties/<int:pk>/rejoindre/", views.sortie_join, name="sortie-join"),
    path("sorties/<int:pk>/quitter/", views.sortie_leave, name="sortie-leave"),

    # Restaurants
    path("restaurants/", views.restaurants_list, name="restaurants-list"),
    path("restaurants/<slug:city_slug>/<slug:slug>/", views.restaurant_detail, name="restaurant-detail"),
    path("restaurants/<slug:city_slug>/<slug:slug>/photos/", views.restaurant_photos, name="restaurant-photos"),
    path("restaurants/<slug:city_slug>/<slug:slug>/reserver/", views.restaurant_book, name="restaurant-book"),

    # Events
    path("evenements/", views.evenements_list, name="evenements-list"),
    path("evenements/<slug:slug>/", views.evenement_detail, name="evenement-detail"),

    # Villes
    path("villes/", views.villes_list, name="villes-list"),
    path("ville/<slug:city_slug>/", views.ville_detail, name="ville-detail"),

    # Partners
    path("partenaires/", views.partenaires_list, name="partenaires-list"),
    path("devenir-partenaire/", views.devenir_partenaire, name="devenir-partenaire"),
    path("become-partner/", views.devenir_partenaire, name="become-partner"),

    # Profil
    path("profil/", views.profil, name="profil"),
    path("profile/", views.profil, name="profile"),
    path("messages/", views.messages_page, name="messages"),
    path("notifications/", views.notifications_page, name="notifications"),
    path("favorites/", views.favorites_page, name="favorites"),
    path("my-events/", views.my_events_page, name="my-events"),
    path("my-tickets/", views.my_tickets_page, name="my-tickets"),
    path("settings/", views.settings_page, name="settings"),
    path("profil/modifier/", views.profil_modifier, name="profil-modifier"),
    path("profil/reservations/", views.profil_reservations, name="profil-reservations"),

    # Partenaire dashboard
    path("partenaire/", views.partenaire_dashboard, name="partenaire-dashboard"),
    path("partner/dashboard/", views.partenaire_dashboard, name="partner-dashboard"),
    path("partner/events/", views.partner_events_page, name="partner-events"),
    path("partner/events/create/", views.partner_events_create_page, name="partner-events-create"),
    path("partner/bookings/", views.partner_bookings_page, name="partner-bookings"),
    path("partner/bookings/restaurants/<int:booking_id>/decision/", views.partner_restaurant_booking_decision, name="partner-restaurant-booking-decision"),
    path("partner/requests/", views.partner_requests_page, name="partner-requests"),
    path("partner/analytics/", views.partner_analytics_page, name="partner-analytics"),
    path("partner/payments/", views.partner_payments_page, name="partner-payments"),
    path("partner/settings/", views.partner_settings_page, name="partner-settings"),

    # Nightlife dashboard
    path("nightlife/dashboard/", views.nightlife_dashboard, name="nightlife-dashboard"),
    path("nightlife/events/", views.nightlife_events_page, name="nightlife-events"),
    path("nightlife/events/create/", views.nightlife_events_create_page, name="nightlife-events-create"),
    path("nightlife/analytics/", views.nightlife_analytics_page, name="nightlife-analytics"),
    path("nightlife/tickets/", views.nightlife_tickets_page, name="nightlife-tickets"),
    path("nightlife/tickets/scan/", views.nightlife_ticket_scan_page, name="nightlife-ticket-scan"),
    path("nightlife/promotions/", views.nightlife_promotions_page, name="nightlife-promotions"),

    # Platform administration
    path("admin/", views.admin_dashboard, name="platform-admin"),
    path("admin/users/", views.admin_users_page, name="platform-admin-users"),
    path("admin/partners/", views.admin_partners_page, name="platform-admin-partners"),
    path("admin/events/", views.admin_events_page, name="platform-admin-events"),
    path("admin/reports/", views.admin_reports_page, name="platform-admin-reports"),
    path("admin/payments/", views.admin_payments_page, name="platform-admin-payments"),
    path("admin/ads/", views.admin_ads_page, name="platform-admin-ads"),
    path("admin/analytics/", views.admin_analytics_page, name="platform-admin-analytics"),

    # Payment callback pages
    path("payment/success/", views.payment_success_page, name="payment-success"),
    path("payment/cancel/", views.payment_cancel_page, name="payment-cancel"),

    # Legal / static pages
    path("<slug:slug>/", views.legal_page, name="legal-page"),
]
