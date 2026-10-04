#!/bin/bash
# Deploy logistics email report to Cloud Run + Cloud Scheduler
# Usage: bash deploy.sh

PROJECT=frido-429506
REGION=asia-south1
SERVICE=logistics-report
IMAGE=gcr.io/$PROJECT/$SERVICE
EMAIL_LIST="pranjal.t@myfrido.com,suraj.s@myfrido.com,mukesh.c@myfrido.com,tushar.g@myfrido.com,yash.p@myfrido.com,abhay.p@myfrido.com,yash.s@myfrido.com"

echo "Building image..."
gcloud builds submit --tag $IMAGE .

echo "Deploying to Cloud Run..."
gcloud run deploy $SERVICE \
  --image $IMAGE \
  --region $REGION \
  --platform managed \
  --no-allow-unauthenticated \
  --set-env-vars "EMAIL_TO=$EMAIL_LIST" \
  --set-env-vars "FROM_EMAIL=data.team@myfrido.com" \
  --set-secrets "OTP_FRIDO_TENANT_ID=OTP_FRIDO_TENANT_ID:latest,OTP_FRIDO_CLIENT_ID=OTP_FRIDO_CLIENT_ID:latest,OTP_FRIDO_CLIENT_SECRET=OTP_FRIDO_CLIENT_SECRET:latest,GCP_CREDENTIALS=GCP_CREDENTIALS:latest" \
  --memory 1Gi \
  --timeout 540

echo "Getting service URL..."
SERVICE_URL=$(gcloud run services describe $SERVICE --region $REGION --format 'value(status.url)')
echo "Service URL: $SERVICE_URL"

echo "Setting up Cloud Scheduler (12:00 PM IST = 06:30 UTC)..."
gcloud scheduler jobs delete logistics-report-daily --location $REGION --quiet 2>/dev/null || true

gcloud scheduler jobs create http logistics-report-daily \
  --location $REGION \
  --schedule "30 6 * * *" \
  --time-zone "UTC" \
  --uri "$SERVICE_URL" \
  --http-method GET \
  --oidc-service-account-email "$(gcloud iam service-accounts list --filter='email~compute' --format='value(email)' | head -1)" \
  --description "Frido Logistics & Ops Report — daily at 12:00 PM IST"

echo "Done. Scheduler set for 12:00 PM IST (06:30 UTC) daily."
