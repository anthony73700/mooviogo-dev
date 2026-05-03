"""
Management command: seed_demo
Populates the DB with realistic French demo data:
  - 4 demo users
  - 12 restaurants (with Unsplash cover photos)
  - time slots for each restaurant
  - 10 sorties communautaires (with cover photos)
  - participants on each sortie

Usage:
    python manage.py seed_demo
    python manage.py seed_demo --reset   # clears existing demo data first
"""

import datetime
import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from apps.events.models import Event
from apps.partners.models import Partner
from apps.restaurants.models import RestaurantTimeSlot, RestaurantVenue
from apps.sorties.models import Sortie, SortieParticipant

User = get_user_model()

# ─────────────────────────────────────────────────────────────────────────────
# DATA
# ─────────────────────────────────────────────────────────────────────────────

USERS = [
    {"username": "sophie_m", "email": "sophie@demo.mv", "display_name": "Sophie M.", "city": "Paris", "password": "demo1234!"},
    {"username": "lucas_r",  "email": "lucas@demo.mv",  "display_name": "Lucas R.", "city": "Lyon",  "password": "demo1234!"},
    {"username": "camille_b","email": "camille@demo.mv","display_name": "Camille B.","city": "Marseille","password": "demo1234!"},
    {"username": "theo_v",   "email": "theo@demo.mv",   "display_name": "Théo V.",  "city": "Paris", "password": "demo1234!"},
]

RESTAURANTS = [
    {
        "name": "Le Perchoir Marais",
        "city_slug": "paris",
        "city_label": "Paris",
        "address": "14 Rue Crespin du Gast, 75011 Paris",
        "cuisine_type": "Cocktails & rooftop",
        "price_range": "€€€",
        "description": "Bar rooftop iconique avec vue panoramique sur les toits de Paris. Cocktails créatifs, ambiance electro chic.",
        "cover_image_url": "https://images.unsplash.com/photo-1470337458703-46ad1756a187?w=800&q=80",
    },
    {
        "name": "Septime",
        "city_slug": "paris",
        "city_label": "Paris",
        "address": "80 Rue de Charonne, 75011 Paris",
        "cuisine_type": "Bistronomie",
        "price_range": "€€€",
        "description": "Table de référence du 11e. Cuisine de marché sensible et précise, cave naturelle remarquable.",
        "cover_image_url": "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=800&q=80",
    },
    {
        "name": "Pink Mamma",
        "city_slug": "paris",
        "city_label": "Paris",
        "address": "20 Bis Rue de Douai, 75009 Paris",
        "cuisine_type": "Italien",
        "price_range": "€€",
        "description": "Temple de la cuisine italienne sur 5 étages à Pigalle. Pâtes fraîches, pizzas napolitaines et ambiance festive.",
        "cover_image_url": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=800&q=80",
    },
    {
        "name": "Noto",
        "city_slug": "paris",
        "city_label": "Paris",
        "address": "19 Rue Henri Monnier, 75009 Paris",
        "cuisine_type": "Japonais fusion",
        "price_range": "€€",
        "description": "Izakaya moderne à South Pigalle. Petites assiettes japonaises à partager, saké naturel et ambiance bar.",
        "cover_image_url": "https://images.unsplash.com/photo-1579871494447-9811cf80d66c?w=800&q=80",
    },
    {
        "name": "Le Café des Fédérations",
        "city_slug": "lyon",
        "city_label": "Lyon",
        "address": "8 Rue du Major Martin, 69001 Lyon",
        "cuisine_type": "Bouchon lyonnais",
        "price_range": "€€",
        "description": "Bouchon incontournable du Vieux-Lyon. Quenelles, andouillette et tablier de sapeur dans une salle boisée authentique.",
        "cover_image_url": "https://images.unsplash.com/photo-1424847651672-bf20a4b0982b?w=800&q=80",
    },
    {
        "name": "Takao Takano",
        "city_slug": "lyon",
        "city_label": "Lyon",
        "address": "33 Rue du Président Carnot, 69002 Lyon",
        "cuisine_type": "Gastronomique",
        "price_range": "€€€",
        "description": "2 étoiles Michelin. Le chef Takao Takano signe une cuisine créative et épurée, mêlant rigueur japonaise et terroir lyonnais.",
        "cover_image_url": "https://images.unsplash.com/photo-1544025162-d76694265947?w=800&q=80",
    },
    {
        "name": "L'Esquinade",
        "city_slug": "marseille",
        "city_label": "Marseille",
        "address": "3 Rue de la Charité, 13002 Marseille",
        "cuisine_type": "Méditerranéen",
        "price_range": "€€",
        "description": "Cuisine méditerranéenne généreuse dans le Panier. Poissons du matin, légumes locaux, terrasse ombragée.",
        "cover_image_url": "https://images.unsplash.com/photo-1559339352-11d035aa65de?w=800&q=80",
    },
    {
        "name": "Le Ventre de l'Architecte",
        "city_slug": "marseille",
        "city_label": "Marseille",
        "address": "Unité d'Habitation Le Corbusier, 13008 Marseille",
        "cuisine_type": "Gastronomique",
        "price_range": "€€€",
        "description": "Restaurant perché au 8e étage de la Cité Radieuse de Le Corbusier. Vue imprenable, cuisine inventive.",
        "cover_image_url": "https://images.unsplash.com/photo-1466978913421-dad2ebd01d17?w=800&q=80",
    },
    {
        "name": "Le Dandy",
        "city_slug": "bordeaux",
        "city_label": "Bordeaux",
        "address": "23 Allées de Tourny, 33000 Bordeaux",
        "cuisine_type": "Bistrot français",
        "price_range": "€€",
        "description": "Belle brasserie bordelaise face aux allées de Tourny. Steak frites parfait, belle sélection de Bordeaux au verre.",
        "cover_image_url": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=800&q=80",
    },
    {
        "name": "Soif Bar à Vins",
        "city_slug": "bordeaux",
        "city_label": "Bordeaux",
        "address": "8 Rue des Remparts, 33000 Bordeaux",
        "cuisine_type": "Bar à vins naturels",
        "price_range": "€€",
        "description": "Bar à vins naturels dans la vieille ville. Planches, fromages et petites assiettes. Ambiance cave conviviale.",
        "cover_image_url": "https://images.unsplash.com/photo-1510812431401-41d2bd2722f3?w=800&q=80",
    },
    {
        "name": "Le Comptoir du Marché",
        "city_slug": "nantes",
        "city_label": "Nantes",
        "address": "12 Rue des Halles, 44000 Nantes",
        "cuisine_type": "Bistronomie",
        "price_range": "€€",
        "description": "Cuisine de marché dans le centre de Nantes. Menu court, produits locaux, ardoise qui change chaque semaine.",
        "cover_image_url": "https://images.unsplash.com/photo-1550966871-3ed3cbe818b5?w=800&q=80",
    },
    {
        "name": "La Winery Rooftop",
        "city_slug": "paris",
        "city_label": "Paris",
        "address": "15 Rue des Martyrs, 75009 Paris",
        "cuisine_type": "Wine bar & tapas",
        "price_range": "€€",
        "description": "Wine bar branché à SoPi. 200 références naturelles, tapas espagnoles et vue terrasse sur le quartier.",
        "cover_image_url": "https://images.unsplash.com/photo-1482275548304-a58859dc31b7?w=800&q=80",
    },
]

EVENTS = [
    {
        "title": "Mooviogo Night — Soirée Rooftop Paris",
        "city": "Paris",
        "location": "Rooftop confidentiel, 11e arrondissement",
        "description": "La soirée officielle Mooviogo revient ! DJ set, cocktails signés, rencontres entre membres de la communauté. Entrée incluse dans l'abonnement premium. Dress code : chic décontracté.",
        "cover_image_url": "https://images.unsplash.com/photo-1533174072545-7a4b6ad7a6c3?w=800&q=80",
        "price": 1500,
        "max_participants": 200,
        "days_ahead": 7,
    },
    {
        "title": "Mooviogo Summer Fest — Lyon",
        "city": "Lyon",
        "location": "Parc de la Tête d'Or, Pelouse Centrale",
        "description": "Festival en plein air organisé par Mooviogo. 3 scènes musicales, food trucks locaux, zone détente et stands partenaires. Entrée gratuite, restauration sur place.",
        "cover_image_url": "https://images.unsplash.com/photo-1506157786151-b8491531f063?w=800&q=80",
        "price": 0,
        "max_participants": 1500,
        "days_ahead": 14,
    },
    {
        "title": "Apéro Réseau Mooviogo — Bordeaux",
        "city": "Bordeaux",
        "location": "Darwin Éco-système, Quai des Queyries",
        "description": "Rencontre networking décontractée entre membres et partenaires Mooviogo. Vins de Bordeaux, fromages locaux, ambiance chill. Idéal pour élargir ton cercle.",
        "cover_image_url": "https://images.unsplash.com/photo-1528605248644-14dd04022da1?w=800&q=80",
        "price": 0,
        "max_participants": 80,
        "days_ahead": 5,
    },
    {
        "title": "Mooviogo Run — 10km Nocturne Marseille",
        "city": "Marseille",
        "location": "Départ Vieux-Port, Quai de Rive Neuve",
        "description": "Course nocturne le long du littoral marseillais, organisée par la communauté Mooviogo. Parcours illuminé, ravitaillement, ambiance musicale et afterrun au bar.",
        "cover_image_url": "https://images.unsplash.com/photo-1461897104016-0b3b00cc81ee?w=800&q=80",
        "price": 1000,
        "max_participants": 300,
        "days_ahead": 10,
    },
    {
        "title": "Mooviogo x Art Contemporain — Vernissage Nantes",
        "city": "Nantes",
        "location": "Lieu Unique, Quai Ferdinand Favre",
        "description": "Soirée vernissage en partenariat avec le Lieu Unique. Découverte des œuvres de 5 artistes nantais émergents, verre de bienvenue offert, DJ ambient.",
        "cover_image_url": "https://images.unsplash.com/photo-1531243269054-5ebf6f34081e?w=800&q=80",
        "price": 0,
        "max_participants": 120,
        "days_ahead": 6,
    },
    {
        "title": "Tournoi Jeux Vidéo Mooviogo — Paris",
        "city": "Paris",
        "location": "La Station Gare des Mines, 18e",
        "description": "Tournoi officiel Mooviogo sur FIFA, Tekken et Mario Kart. Dotations à la clé, bonne ambiance et bar sur place. Inscription libre, viens juste avec tes skills.",
        "cover_image_url": "https://images.unsplash.com/photo-1542751371-adc38448a05e?w=800&q=80",
        "price": 500,
        "max_participants": 64,
        "days_ahead": 9,
    },
    {
        "title": "Mooviogo Plage — Journée Beach à Nice",
        "city": "Nice",
        "location": "Plage Lenval, Promenade des Anglais",
        "description": "Journée communautaire sur la plage. Volley, stand-up paddle, pique-nique géant et afterwork au soleil couchant. Transport Mooviogo depuis le centre-ville.",
        "cover_image_url": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=800&q=80",
        "price": 0,
        "max_participants": 100,
        "days_ahead": 12,
    },
    {
        "title": "Conférence Mooviogo — L'avenir du lien social",
        "city": "Paris",
        "location": "Station F, 5 Parvis Alan Turing, 75013",
        "description": "Tables rondes et keynotes sur le lien social à l'ère numérique, les nouvelles formes de communautés et l'économie des expériences. Intervenants issus de la tech, la sociologie et l'entrepreneuriat.",
        "cover_image_url": "https://images.unsplash.com/photo-1540575467063-178a50c2df87?w=800&q=80",
        "price": 2000,
        "max_participants": 250,
        "days_ahead": 20,
    },
]

PARTNERS = [
    {
        "name": "Zone Paintball Paris",
        "city": "Paris",
        "address": "45 Rue de la Roquette, 75011 Paris",
        "category": "Paintball",
        "short_description": "Terrain indoor de paintball au cœur de Paris. Équipement pro, scénarios variés.",
        "description": "Zone Paintball Paris propose 6 terrains indoor thématisés — forêt, urbain, zombie… Idéal pour enterrements de vie, team-buildings et anniversaires. Équipement haute gamme fourni, formules à partir de 25€/pers.",
        "cover_image_url": "https://images.unsplash.com/photo-1551698618-1dfe5d97d256?w=800&q=80",
        "website": "https://example.com",
    },
    {
        "name": "Karting Indoor Lyon",
        "city": "Lyon",
        "address": "12 Rue de la Soie, 69100 Villeurbanne",
        "category": "Karting",
        "short_description": "Circuit indoor 500m, karts électriques 13kW. Sensations garanties toute l'année.",
        "description": "Le plus grand circuit de karting indoor de la région lyonnaise. Karts électriques silencieux et rapides, chronométrage en temps réel, podium, bar et restauration sur place. Sessions de 10 à 30 min.",
        "cover_image_url": "https://images.unsplash.com/photo-1558981403-c5f9899a28bc?w=800&q=80",
        "website": "https://example.com",
    },
    {
        "name": "Escape Game Enigma Marseille",
        "city": "Marseille",
        "address": "8 Cours Julien, 13006 Marseille",
        "category": "Escape Game",
        "short_description": "4 salles immersives, de 60 min chacune. Scénarios horrifique, polar, aventure.",
        "description": "Enigma vous plonge dans des univers inédits : prison médiévale, enquête policière, vaisseau spatial… Groupes de 2 à 6 joueurs. Séances tous les jours de 10h à 23h. Réservation conseillée.",
        "cover_image_url": "https://images.unsplash.com/photo-1590077428593-a55bb07c4665?w=800&q=80",
        "website": "https://example.com",
    },
    {
        "name": "Bowling King Bordeaux",
        "city": "Bordeaux",
        "address": "Rue du Stade Chaban, 33000 Bordeaux",
        "category": "Bowling",
        "short_description": "24 pistes, laser bowl vendredi & samedi, bar, burgers et billard.",
        "description": "Bowling King c'est 24 pistes climatisées, une ambiance laser le week-end, un bar cocktails et une cuisine américaine. Tarifs dégressifs en groupe, privatisation possible pour événements.",
        "cover_image_url": "https://images.unsplash.com/photo-1545809759-afeeb6e6a27e?w=800&q=80",
        "website": "https://example.com",
    },
    {
        "name": "Laser Game Evolution Paris",
        "city": "Paris",
        "address": "30 Boulevard Haussmann, 75009 Paris",
        "category": "Laser Game",
        "short_description": "Arène de 800m², effets spéciaux, musique immersive. Le laser game nouvelle génération.",
        "description": "Une arène futuriste de 800m² sur 2 niveaux. Équipements dernière génération, capteurs HD, effets de fumée et musique spatiale. Partis de 4 à 20 joueurs. Idéal pour anniversaires & EVG.",
        "cover_image_url": "https://images.unsplash.com/photo-1563198804-b144dfc1661c?w=800&q=80",
        "website": "https://example.com",
    },
    {
        "name": "Accrobranche & Aventure Nantes",
        "city": "Nantes",
        "address": "Forêt de la Barberie, Route de la Forêt, 44000 Nantes",
        "category": "Accrobranche",
        "short_description": "12 parcours dans les arbres, tyrolienne géante 200m, via ferrata.",
        "description": "Parc aventure en forêt avec 12 parcours classés de vert à noir. Tyrolienne panoramique de 200m, mur d'escalade et initiation via ferrata. Ouvert week-ends et vacances scolaires.",
        "cover_image_url": "https://images.unsplash.com/photo-1551632811-561732d1e306?w=800&q=80",
        "website": "https://example.com",
    },
    {
        "name": "Virtual Room VR Paris",
        "city": "Paris",
        "address": "18 Rue du Temple, 75004 Paris",
        "category": "Réalité Virtuelle",
        "short_description": "Expériences VR multi-joueurs en free-roaming. Jusqu'à 6 joueurs simultanément.",
        "description": "Virtual Room est le pioneer du jeu VR multi-joueurs en free-roaming à Paris. Casques dernière génération, scénarios coopératifs exclusifs. Sessions de 30 min à 1h. Aucune expérience VR requise.",
        "cover_image_url": "https://images.unsplash.com/photo-1617802690992-15d93263d3a9?w=800&q=80",
        "website": "https://example.com",
    },
    {
        "name": "Axe Throwing Club Lyon",
        "city": "Lyon",
        "address": "5 Rue Sergent Blandan, 69001 Lyon",
        "category": "Lancer de hache",
        "short_description": "Lancer de hache encadré par des coachs pros. Apéro bière artisanale inclus.",
        "description": "10 cibles, des haches authentiques, des coachs certifiés et une bière artisanale pour fêter chaque bullseye. Groupes de 2 à 30 personnes. Aucune expérience nécessaire — on vous apprend en 5 min.",
        "cover_image_url": "https://images.unsplash.com/photo-1541534741688-6078c6bfb5c5?w=800&q=80",
        "website": "https://example.com",
    },
]

SORTIES = [
    {
        "title": "Apéro coucher de soleil au Sacré-Cœur",
        "city": "Paris",
        "type": "COMMUNAUTAIRE",
        "description": "On se retrouve sur les marches du Sacré-Cœur pour un apéro entre inconnus sympa. Bouteille de vin, fromage et bonne humeur. Venez comme vous êtes !",
        "location": "Parvis du Sacré-Cœur, Montmartre",
        "price": 0,
        "is_free": True,
        "max_participants": 20,
        "cover_image_url": "https://images.unsplash.com/photo-1499856871958-5b9627545d1a?w=800&q=80",
        "days_ahead": 2,
    },
    {
        "title": "Soirée jeux de société Opéra",
        "city": "Paris",
        "type": "COMMUNAUTAIRE",
        "description": "Café-jeux dans le 9e, on loue des jeux sur place (Catane, Mysterium, Codenames…). Parfait pour rencontrer des gens fun sans prise de tête.",
        "location": "Café Joyeux, 9e arrondissement",
        "price": 800,
        "is_free": False,
        "max_participants": 12,
        "cover_image_url": "https://images.unsplash.com/photo-1606503153255-59d8b8b82176?w=800&q=80",
        "days_ahead": 3,
    },
    {
        "title": "Randonnée urbaine street art Belleville",
        "city": "Paris",
        "type": "COMMUNAUTAIRE",
        "description": "Balade guidée par un habitant dans le quartier street art de Belleville. 2h de marche, plein de découvertes visuelles. On finit autour d'un verre.",
        "location": "Métro Belleville (sortie Bd de Belleville)",
        "price": 0,
        "is_free": True,
        "max_participants": 15,
        "cover_image_url": "https://images.unsplash.com/photo-1561214115-f2f134cc4912?w=800&q=80",
        "days_ahead": 5,
    },
    {
        "title": "Soirée DJ rooftop Oberkampf",
        "city": "Paris",
        "type": "PARTENAIRE",
        "description": "Soirée electro sur un rooftop du 11e. DJ set de 21h à 02h, vue sur Paris, open bar premium inclus dans le ticket.",
        "location": "Rooftop confidentiel — adresse envoyée après réservation",
        "price": 2500,
        "is_free": False,
        "max_participants": 80,
        "cover_image_url": "https://images.unsplash.com/photo-1429962714451-bb934ecdc4ec?w=800&q=80",
        "days_ahead": 4,
    },
    {
        "title": "Brunch veggie entre gourmands",
        "city": "Lyon",
        "type": "COMMUNAUTAIRE",
        "description": "Brunch collectif dans un appartement du 1er. Chacun ramène quelque chose : viennoiseries, fruits, granola maison. Vibe zen et conviviale.",
        "location": "Croix-Rousse, Lyon 1er",
        "price": 0,
        "is_free": True,
        "max_participants": 10,
        "cover_image_url": "https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=800&q=80",
        "days_ahead": 1,
    },
    {
        "title": "Ciné en plein air Parc de la Tête d'Or",
        "city": "Lyon",
        "type": "COMMUNAUTAIRE",
        "description": "Projection de Midnight in Paris sous les étoiles au parc. Apporte ta couverture et ton pique-nique. On se retrouve à l'entrée Gambetta à 21h.",
        "location": "Parc de la Tête d'Or, entrée Gambetta",
        "price": 0,
        "is_free": True,
        "max_participants": 30,
        "cover_image_url": "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=800&q=80",
        "days_ahead": 6,
    },
    {
        "title": "Soirée karaoké Vieux-Port",
        "city": "Marseille",
        "type": "COMMUNAUTAIRE",
        "description": "Karaoké privatisé pour notre groupe au bord du Vieux-Port. On chante, on rigole, on se fait des amis. Playlist variée.",
        "location": "Bar Le Trolley, Vieux-Port",
        "price": 1000,
        "is_free": False,
        "max_participants": 25,
        "cover_image_url": "https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?w=800&q=80",
        "days_ahead": 3,
    },
    {
        "title": "Paddle lever de soleil Côte d'Azur",
        "city": "Marseille",
        "type": "COMMUNAUTAIRE",
        "description": "On se retrouve à l'aube pour une session paddle au Frioul. Eau turquoise garantie. Débutants acceptés, matériel fourni.",
        "location": "Embarcadère Frioul, Quai de la Fraternité",
        "price": 1500,
        "is_free": False,
        "max_participants": 8,
        "cover_image_url": "https://images.unsplash.com/photo-1530053969600-caed2596d242?w=800&q=80",
        "days_ahead": 7,
    },
    {
        "title": "Dégustation vins de Bordeaux entre passionnés",
        "city": "Bordeaux",
        "type": "COMMUNAUTAIRE",
        "description": "Cave privée, 6 flacons, un sommelier passionné. On commente, on débat, on découvre. Places limitées — ambiance intimiste assurée.",
        "location": "Cave Bordelaise, Quartier Saint-Pierre",
        "price": 3500,
        "is_free": False,
        "max_participants": 8,
        "cover_image_url": "https://images.unsplash.com/photo-1510812431401-41d2bd2722f3?w=800&q=80",
        "days_ahead": 5,
    },
    {
        "title": "Tournoi de pétanque & pastis",
        "city": "Marseille",
        "type": "COMMUNAUTAIRE",
        "description": "Tournoi de pétanque en bord de mer, apéro pastis compris. Esprit bouliste authentique, débutants bienvenus. On joue en binômes tirés au sort.",
        "location": "Plage des Catalans, Marseille",
        "price": 500,
        "is_free": False,
        "max_participants": 24,
        "cover_image_url": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=800&q=80",
        "days_ahead": 2,
    },
]

# ─────────────────────────────────────────────────────────────────────────────


class Command(BaseCommand):
    help = "Seed the database with demo restaurants, sorties and users."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing demo data before seeding.",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            self.stdout.write("🗑  Resetting demo data…")
            SortieParticipant.objects.all().delete()
            Sortie.objects.all().delete()
            RestaurantTimeSlot.objects.all().delete()
            RestaurantVenue.objects.all().delete()
            Partner.objects.all().delete()
            Event.objects.filter(is_partner_event=False).delete()
            User.objects.filter(email__endswith="@demo.mv").delete()

        # ── Users ──────────────────────────────────────────────────────────
        self.stdout.write("👥  Creating demo users…")
        users = []
        for u in USERS:
            obj, created = User.objects.get_or_create(
                email=u["email"],
                defaults={
                    "username": u["username"],
                    "display_name": u["display_name"],
                    "city": u["city"],
                    "is_active": True,
                },
            )
            if created:
                obj.set_password(u["password"])
                obj.save()
            users.append(obj)
        self.stdout.write(self.style.SUCCESS(f"   ✓ {len(users)} users ready"))

        # ── Restaurants ────────────────────────────────────────────────────
        self.stdout.write("🍽  Creating demo restaurants…")
        venues = []
        for r in RESTAURANTS:
            slug = slugify(r["name"])
            obj, _ = RestaurantVenue.objects.get_or_create(
                city_slug=r["city_slug"],
                slug=slug,
                defaults={
                    "name": r["name"],
                    "city_label": r["city_label"],
                    "address": r["address"],
                    "cuisine_type": r["cuisine_type"],
                    "price_range": r["price_range"],
                    "description": r["description"],
                    "cover_image_url": r["cover_image_url"],
                    "is_active": True,
                },
            )
            venues.append(obj)

            # Add time slots for the next 7 days
            today = datetime.date.today()
            for day_offset in range(1, 8):
                slot_date = today + datetime.timedelta(days=day_offset)
                for slot_time in [
                    datetime.time(12, 30),
                    datetime.time(13, 0),
                    datetime.time(19, 30),
                    datetime.time(20, 0),
                    datetime.time(20, 30),
                    datetime.time(21, 0),
                ]:
                    RestaurantTimeSlot.objects.get_or_create(
                        venue=obj,
                        date=slot_date,
                        time=slot_time,
                        defaults={
                            "capacity": random.choice([4, 6, 8]),
                            "confirmed_count": random.randint(0, 2),
                            "status": "OPEN",
                        },
                    )

        self.stdout.write(self.style.SUCCESS(f"   ✓ {len(venues)} restaurants + time slots ready"))

        # ── Sorties ────────────────────────────────────────────────────────
        self.stdout.write("🎉  Creating demo sorties…")
        for s in SORTIES:
            creator = random.choice(users)
            slug_base = slugify(s["title"])
            slug = slug_base
            counter = 1
            while Sortie.objects.filter(slug=slug).exists():
                slug = f"{slug_base}-{counter}"
                counter += 1

            starts_at = timezone.now() + datetime.timedelta(
                days=s["days_ahead"],
                hours=random.randint(0, 4),
            )

            sortie, created = Sortie.objects.get_or_create(
                slug=slug,
                defaults={
                    "title": s["title"],
                    "city": s["city"],
                    "type": s["type"],
                    "description": s["description"],
                    "location": s.get("location", ""),
                    "price": s["price"],
                    "is_free": s["is_free"],
                    "max_participants": s["max_participants"],
                    "starts_at": starts_at,
                    "cover_image_url": s["cover_image_url"],
                    "status": "OPEN",
                    "creator": creator,
                },
            )

            if created:
                # Add 2–5 random participants
                other_users = [u for u in users if u != creator]
                for participant in random.sample(other_users, min(random.randint(1, 3), len(other_users))):
                    SortieParticipant.objects.get_or_create(
                        sortie=sortie,
                        user=participant,
                        defaults={"status": "CONFIRMED"},
                    )

        sorties_count = Sortie.objects.count()
        self.stdout.write(self.style.SUCCESS(f"   ✓ {sorties_count} sorties ready"))

        # ── Partners ───────────────────────────────────────────────────────
        self.stdout.write("🤝  Creating demo partners…")
        for i, p in enumerate(PARTNERS):
            slug = slugify(p["name"])
            Partner.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": p["name"],
                    "city": p["city"],
                    "address": p.get("address", ""),
                    "category": p["category"],
                    "short_description": p["short_description"],
                    "description": p["description"],
                    "cover_image_url": p["cover_image_url"],
                    "website": p.get("website", ""),
                    "status": Partner.Status.ACTIVE,
                    "is_verified": True,
                    "owner": None,
                },
            )
        partners_count = Partner.objects.count()
        self.stdout.write(self.style.SUCCESS(f"   ✓ {partners_count} partners ready"))

        # ── Events ─────────────────────────────────────────────────────────
        self.stdout.write("🎭  Creating demo events…")
        for e in EVENTS:
            slug_base = slugify(e["title"])
            slug = slug_base
            counter = 1
            while Event.objects.filter(slug=slug).exists():
                slug = f"{slug_base}-{counter}"
                counter += 1
            starts_at = timezone.now() + datetime.timedelta(days=e["days_ahead"], hours=20)
            ends_at = starts_at + datetime.timedelta(hours=4)
            Event.objects.get_or_create(
                slug=slug,
                defaults={
                    "title": e["title"],
                    "city": e["city"],
                    "location": e["location"],
                    "description": e["description"],
                    "cover_image_url": e["cover_image_url"],
                    "price": e["price"],
                    "max_participants": e["max_participants"],
                    "starts_at": starts_at,
                    "ends_at": ends_at,
                    "status": Event.Status.PUBLISHED,
                    "is_partner_event": False,
                },
            )
        events_count = Event.objects.filter(is_partner_event=False).count()
        self.stdout.write(self.style.SUCCESS(f"   ✓ {events_count} events ready"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("✅  Demo seed complete!"))
        self.stdout.write("   Login with: sophie@demo.mv / demo1234!")
        self.stdout.write(f"   🌐 http://51.178.80.250:8000/")
