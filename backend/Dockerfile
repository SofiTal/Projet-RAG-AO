# Utilise une image Python officielle
FROM python:3.10-slim

# Définit le dossier de travail
WORKDIR /app

# Copie seulement les fichiers de dépendances pour profiter du cache Docker
COPY requirements.txt .

# Mise à jour de pip et installation des dépendances
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copie le reste du code backend dans le conteneur
COPY . .

# Expose le port utilisé par FastAPI
EXPOSE 8000

# Commande de démarrage de l'application FastAPI
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
