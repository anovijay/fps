#!/usr/bin/env bash
set -euo pipefail

# Configuration
PROJECT_ID="rhea-459720"
REGION="us-central1"
SERVICE_NAME="fps-simplified"
IMAGE_NAME="fps-simplified"
IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${SERVICE_NAME}/${IMAGE_NAME}"

echo "Building and pushing Docker image: $IMAGE_URI"
docker buildx build --platform linux/amd64 -f Dockerfile-simplified -t "$IMAGE_URI" --push .

echo "Deploying simplified Cloud Run service: $SERVICE_NAME"
gcloud run deploy "$SERVICE_NAME" \
  --image="$IMAGE_URI" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --allow-unauthenticated \
  --port=8080 \
  --memory=1Gi \
  --cpu=1 \
  --max-instances=10 \
  --timeout=300 \
  --set-env-vars "PORT=8080" \
  --set-env-vars "OPENAI_API_KEY=${OPENAI_API_KEY}"

echo "Deployment complete! Service is running at:"
gcloud run services describe "$SERVICE_NAME" --region="$REGION" --project="$PROJECT_ID" --format="value(status.url)" 