# Auth OTP + OAuth API (Django)

Date: 2026-05-15

## Endpoints OTP telephone

- POST /api/v1/auth/phone/request-otp/
  - body: {"phone": "+33612345678"}
  - response: {"detail": "Code OTP envoye."}
  - En DEBUG: response inclut debug_code pour QA locale.

- POST /api/v1/auth/phone/verify-otp/
  - body: {"phone": "+33612345678", "code": "123456"}
  - response: {"phone_verification_token": "..."}

## Inscription API protegee OTP

- POST /api/v1/auth/register/
  - body requis:
    - email
    - username
    - display_name (optionnel)
    - birth_date (>=18)
    - phone
    - phone_verification_token
    - password
  - comportement:
    - le token OTP est consomme en creation de compte.

- POST /api/v1/users/register/
  - Aligne sur les memes contraintes OTP (anti-bypass).

## Social login OAuth

- POST /api/v1/auth/social-login/
  - provider: google | facebook | apple
  - google/facebook: access_token
  - apple: id_token
  - si utilisateur existant (email): retourne JWT access/refresh
  - si nouvel utilisateur: birth_date + phone + phone_verification_token requis

## Notes de securite

- OTP code TTL: 10 minutes.
- Token de verification OTP TTL: 30 minutes.
- Token OTP consomme a l'inscription pour eviter le rejeu.
