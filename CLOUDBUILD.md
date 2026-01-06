# Google Cloud Build - ARM64 Docker Image

This guide explains how to build ARM64 Docker images using Google Cloud Build.

## Prerequisites

1. **Google Cloud Project** with billing enabled
2. **gcloud CLI** installed and authenticated
3. **Cloud Build API** enabled
4. **Container Registry or Artifact Registry** enabled

## Initial Setup

### 1. Install and Configure gcloud

```bash
# Install gcloud CLI (if not already installed)
# https://cloud.google.com/sdk/docs/install

# Authenticate
gcloud auth login

# Set your project ID
gcloud config set project YOUR_PROJECT_ID
```

### 2. Enable Required APIs

```bash
# Enable Cloud Build API
gcloud services enable cloudbuild.googleapis.com

# Enable Container Registry
gcloud services enable containerregistry.googleapis.com

# OR enable Artifact Registry (newer, recommended)
gcloud services enable artifactregistry.googleapis.com
```

### 3. Grant Cloud Build Permissions

```bash
# Get your project number
PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project) --format='value(projectNumber)')

# Grant Cloud Build permission to push images
gcloud projects add-iam-policy-binding $(gcloud config get-value project) \
  --member=serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com \
  --role=roles/storage.admin
```

## Build Commands

### Option 1: Manual Build (Cloud Build)

```bash
# Build using cloudbuild.yaml
gcloud builds submit --config cloudbuild.yaml .
```

### Option 2: Build with Custom Tags

```bash
# Build with specific version tag
gcloud builds submit \
  --config cloudbuild.yaml \
  --substitutions=_IMAGE_TAG=v1.0.0 \
  .
```

### Option 3: Build with Artifact Registry

If using Artifact Registry instead of Container Registry, update the image name:

```bash
# Create Artifact Registry repository (one time)
gcloud artifacts repositories create garmin-grafana \
  --repository-format=docker \
  --location=us-central1 \
  --description="Garmin Grafana ARM64 images"

# Build and push to Artifact Registry
gcloud builds submit \
  --config cloudbuild.yaml \
  --substitutions=_IMAGE_NAME=us-central1-docker.pkg.dev/YOUR_PROJECT_ID/garmin-grafana/garmingrafana \
  .
```

## Automated Builds (GitHub/GitLab Integration)

### Connect to GitHub

```bash
# Install Cloud Build app in GitHub
# Go to: https://console.cloud.google.com/cloud-build/triggers

# Create a trigger
gcloud builds triggers create github \
  --repo-name=garmin-grafana \
  --repo-owner=YOUR_GITHUB_USERNAME \
  --branch-pattern=^main$ \
  --build-config=cloudbuild.yaml
```

## Pull Image on Raspberry Pi

After the build completes:

### Using Container Registry (gcr.io)

```bash
# On your Raspberry Pi
# Authenticate (one time)
gcloud auth configure-docker

# Pull the image
docker pull gcr.io/YOUR_PROJECT_ID/garmingrafana:latest
```

### Using Artifact Registry

```bash
# On your Raspberry Pi
# Authenticate (one time)
gcloud auth configure-docker us-central1-docker.pkg.dev

# Pull the image
docker pull us-central1-docker.pkg.dev/YOUR_PROJECT_ID/garmin-grafana/garmingrafana:latest
```

### Make Image Public (Optional)

If you want to pull without authentication:

```bash
# Make Container Registry bucket public
gsutil iam ch allUsers:objectViewer gs://artifacts.YOUR_PROJECT_ID.appspot.com

# OR for Artifact Registry
gcloud artifacts repositories add-iam-policy-binding garmin-grafana \
  --location=us-central1 \
  --member=allUsers \
  --role=roles/artifactregistry.reader
```

## Update docker-compose.yml for Raspberry Pi

```yaml
version: '3'
services:
  garmin-fetch-data:
    # Use GCR image
    image: gcr.io/YOUR_PROJECT_ID/garmingrafana:latest

    # OR Artifact Registry
    # image: us-central1-docker.pkg.dev/YOUR_PROJECT_ID/garmin-grafana/garmingrafana:latest

    container_name: garmin-fetch-data
    restart: unless-stopped
    # ... rest of your config
```

## Verify Build

```bash
# List recent builds
gcloud builds list --limit=5

# Get build logs
gcloud builds log BUILD_ID

# List images in registry
gcloud container images list

# OR for Artifact Registry
gcloud artifacts docker images list us-central1-docker.pkg.dev/YOUR_PROJECT_ID/garmin-grafana
```

## Cost Optimization

Cloud Build free tier includes:
- First 120 build-minutes per day are free
- ARM64 builds typically take 5-10 minutes

To reduce costs:
- Use manual builds instead of automated triggers
- Build only when deploying new versions
- Clean up old images periodically

```bash
# Delete old images (keep last 5)
gcloud container images list-tags gcr.io/YOUR_PROJECT_ID/garmingrafana \
  --format='get(digest)' --limit=999 | \
  tail -n +6 | \
  xargs -I {} gcloud container images delete "gcr.io/YOUR_PROJECT_ID/garmingrafana@{}" --quiet
```

## Running on the Raspberry Pi

```bash
# On your Raspberry Pi
# Authenticate (one time)
gcloud auth configure-docker
```

```bash
docker pull gcr.io/garmingrafana/garmin-fetch-data:latest
```


## Troubleshooting

### Build Fails with "buildx not found"

Update the Cloud Build configuration to use a newer Docker builder image.

### Permission Denied

Ensure Cloud Build service account has proper permissions:
```bash
gcloud projects get-iam-policy $(gcloud config get-value project)
```

### Slow Builds

ARM64 builds use QEMU emulation and are slower. Consider:
- Using a larger machine type (already set to N1_HIGHCPU_8)
- Building less frequently
- Using layer caching

## References

- [Cloud Build Documentation](https://cloud.google.com/build/docs)
- [Multi-platform Builds](https://cloud.google.com/build/docs/building/build-containers#multi-platform)
- [Container Registry](https://cloud.google.com/container-registry/docs)
- [Artifact Registry](https://cloud.google.com/artifact-registry/docs)
