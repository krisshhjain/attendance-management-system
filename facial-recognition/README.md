# Facial recognition service security configuration

The Flask API is an internal service called by Django. It does not use browser
sessions or cookies, so CSRF tokens do not apply. Its `/health` endpoint only
reports service availability. Every enrollment, extraction, and recognition
request requires a bearer token, including requests over loopback.

## Local host development

The service binds to `127.0.0.1:8001` by default. Django's local default URL is
`http://127.0.0.1:8001`. Set the same private `FACE_SERVICE_TOKEN` in the
backend environment and the facial-recognition process for local development.

## Django running in Docker Compose

Compose points the backend to `http://host.docker.internal:8001`. Run the face
service on a specific host interface address reachable from Docker by setting
`FR_BIND_HOST` to that address, and set the same strong, private
`FACE_SERVICE_TOKEN` in the backend's `backend/.env` and in the face service
process environment. The service refuses a non-loopback bind without the token
and rejects unauthenticated API requests on every interface.
Restrict inbound access to the Docker network in the host firewall. Avoid
binding all host interfaces unless network policy requires it.

Do not commit the token or place it in an image. The backend Docker build
excludes local `.env` files.
