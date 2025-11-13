#!/bin/bash
# Test Check-in Server Upload Photo API

echo "=== Testing Check-in Server Upload Photo API ==="
echo ""

# Test 1: Health Check
echo "1. Testing Health Check..."
curl -s http://localhost:3001/api/health | python3 -m json.tool
echo ""

# Test 2: Upload Photo (requires a test image)
echo "2. Testing Upload Photo..."

# Create a simple test image if doesn't exist
if [ ! -f "test_image.jpg" ]; then
    echo "Creating test image..."
    # This will create a simple colored square image
    convert -size 640x480 xc:blue test_image.jpg 2>/dev/null || echo "ImageMagick not installed, skipping image creation"
fi

if [ -f "test_image.jpg" ]; then
    echo "Uploading test image..."
    curl -X POST http://localhost:3001/api/upload-photo \
      -F "image=@test_image.jpg" \
      -F "latitude=13.8180" \
      -F "longitude=100.0365" \
      -F "address=เทศบาลนครนครปฐม, นครปฐม" \
      -F "timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
      -s | python3 -m json.tool
else
    echo "No test image found, skipping upload test"
fi

echo ""
echo "=== Test Complete ==="
