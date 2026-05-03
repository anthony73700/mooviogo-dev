from django.urls import path

from . import views

urlpatterns = [
    # Home
    path("", views.home, name="home"),

    # Auth
    path("connexion/", views.login_view, name="login"),
    path("inscription/", views.signup_view, name="signup"),
    path("deconnexion/", views.logout_view, name="logout"),

    # Sorties
    path("sorties/", views.sorties_list, name="sorties-list"),
    path("sorties/creer/", views.sortie_create, name="sortie-create"),
    path("sorties/<int:pk>/", views.sortie_detail, name="sortie-detail"),
    path("sorties/<int:pk>/rejoindre/", views.sortie_join, name="sortie-join"),
    path("sorties/<int:pk>/quitter/", views.sortie_leave, name="sortie-leave"),

    # Restaurants
    path("restaurants/", views.restaurants_list, name="restaurants-list"),
    path("restaurants/<slug:city_slug>/<slug:slug>/", views.restaurant_detail, name="restaurant-detail"),
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

    # Profil
    path("profil/", views.profil, name="profil"),
    path("profil/modifier/", views.profil_modifier, name="profil-modifier"),
    path("profil/reservations/", views.profil_reservations, name="profil-reservations"),

    # Partenaire dashboard
    path("partenaire/", views.partenaire_dashboard, name="partenaire-dashboard"),

    # Legal / static pages
    path("<slug:slug>/", views.legal_page, name="legal-page"),
]
