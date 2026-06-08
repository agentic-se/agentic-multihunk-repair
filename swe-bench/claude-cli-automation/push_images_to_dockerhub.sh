#!/bin/bash
# Push all claude-eval Docker images to Docker Hub
set -e

DOCKERHUB_REPO="noornashid/maple"
IMAGE_PREFIX="claude-eval"

echo "======================================"
echo "Docker Hub Image Push Script"
echo "======================================"
echo "Target repository: $DOCKERHUB_REPO"
echo ""
echo "Note: If you get authentication errors, run 'docker login' first"
echo ""

# Get all claude-eval images
IMAGES=$(docker images --format "{{.Repository}}:{{.Tag}}" | grep "^claude-eval/" | sort)

if [ -z "$IMAGES" ]; then
    echo "❌ No claude-eval images found!"
    exit 1
fi

# Count total images
TOTAL=$(echo "$IMAGES" | wc -l | tr -d ' ')
echo "Found $TOTAL claude-eval images to push"
echo ""

CURRENT=0
SUCCEEDED=0
FAILED=0

# Process each image
for IMAGE in $IMAGES; do
    CURRENT=$((CURRENT + 1))

    # Extract instance name (e.g., "astropy_1776_astropy-13033")
    INSTANCE_NAME=$(echo "$IMAGE" | sed 's|claude-eval/||' | sed 's|:latest||')

    # Create Docker Hub tag
    HUB_TAG="$DOCKERHUB_REPO:claude-eval-$INSTANCE_NAME"

    echo "[$CURRENT/$TOTAL] Processing: $INSTANCE_NAME"
    echo "  Source: $IMAGE"
    echo "  Target: $HUB_TAG"

    # Tag the image
    if docker tag "$IMAGE" "$HUB_TAG"; then
        echo "  ✓ Tagged successfully"

        # Push to Docker Hub
        echo "  Pushing to Docker Hub..."
        if docker push "$HUB_TAG"; then
            echo "  ✓ Pushed successfully"
            SUCCEEDED=$((SUCCEEDED + 1))
        else
            echo "  ❌ Push failed!"
            FAILED=$((FAILED + 1))
        fi
    else
        echo "  ❌ Tag failed!"
        FAILED=$((FAILED + 1))
    fi

    echo ""
done

echo "======================================"
echo "Summary"
echo "======================================"
echo "Total images: $TOTAL"
echo "Succeeded: $SUCCEEDED"
echo "Failed: $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "✅ All images pushed successfully!"
    echo ""
    echo "You can view them at:"
    echo "https://hub.docker.com/r/$DOCKERHUB_REPO/tags"
else
    echo "⚠️  Some images failed to push"
    exit 1
fi
