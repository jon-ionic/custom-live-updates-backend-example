# Bring your own Appflow
This is a bare-minimum implementation of a custom backend for the Live Updates SDK, using Flask and SQLite. It includes the two endpoints required by the SDK (`check-device` and `manifest-v2`) as well as supporting endpoints for creating and viewing apps, builds, and deployments.

## Usage

### Setup
```bash
# Create a virtual environment
python3 -m venv .

# Activate the environment
source bin/activate

# Install the project dependencies
pip3 install -r requirements.txt

# Run the application
python3 -m gunicorn -w 4 -b 0.0.0.0:3000 app:app
```

### Create an app

Create an app using the /apps endpoint.
```bash
curl --location 'http://localhost:8000/apps' \
  --header 'Content-Type: application/json' \
  --data '{"id": "abcd1234", "name": "test-app"}'
```

View all apps:
```bash
curl --location 'http://localhost:8000/apps'
```

### Create a build

Create a build using the /builds endpoint.
```bash
curl --location 'http://localhost:8000/apps/abcd1234/builds' \
  --header 'Content-Type: application/json' \
  --data '{
      "artifact_url": "https://my-storage-provider.local/live-update-manifest.json",
      "artifact_type": "differential",
      "commit_sha": "123456",
      "commit_message": "initial build",
      "commit_ref": "main"
    }'
```

View all builds: 
```bash
curl --location 'http://localhost:8000/apps/abcd1234/builds'
```

### Create a deployment

Deploy the created build using the /deployments endpoint.

```bash
curl --location 'http://localhost:8000/apps/abcd1234/deployments' \
  --header 'Content-Type: application/json' \
  --data '{
      "build_id": 1,
      "channel_name": "production"
    }'
```

View all deployments:
```bash
curl --location 'http://localhost:8000/apps/abcd1234/deployments'
```

## Plugin Usage

The Live Updates SDK will send requests to the app's `check-device` and `manifest_v2` endpoints when a live update is attempted.

When the plugin's `sync` method is called, it will send a POST request to the `check-device` endpoint with data such as the following:

```bash
curl --location 'http://localhost:8000/apps/abcd1234/channels/check-device' \
  --header 'Content-Type: application/json' \
  --data '{
    "device": {
      "binary_version": "1.0.0",
      "platform": "android",
      "platform_version": "30"
    },
    "app_id": "abcd1234",
    "channel_name": "production",
    "is_portals": false,
    "plugin_version": "6",
    "manifest": true
  }'
```

The endpoint should return a response like the following:
```json
{
    "data": {
        "available": true,
        "build": 1,
        "compatible": true,
        "incompatibleUpdateAvailable": false,
        "partial": false,
        "snapshot": "fdc7c806-ccfa-4c95-a9e3-d8fd44d08076",
        "url": "http://localhost:8000/apps/abcd1234/snapshots/fdc7c806-ccfa-4c95-a9e3-d8fd44d08076/manifest_v2"
    },
    "meta": {
        "status": 200,
        "version": "2.0.0-sdlc-beta.0",
        "request_id": "0ea4c1fb-a8c6-4a38-a206-4abc7f0d3a02"
    }
}
```

If `data.available` is true, the plugin will send a GET request to the `data.url`, which is the app's `manifest_v2` endpoint.

The `manifest_v2` endpoint should redirect to the snapshot/build's artifact URL.
```bash
curl -s -L -D - 'http://localhost:8000/apps/abcd1234/snapshots/fdc7c806-ccfa-4c95-a9e3-d8fd44d08076/manifest_v2' -o /dev/null -w '%{url_effective}'

HTTP/1.1 302 FOUND
Server: gunicorn
Date: Sun, 15 Jun 2025 18:11:16 GMT
Connection: close
Content-Type: text/html; charset=utf-8
Content-Length: 305
Location: https://my-storage-provider.local/live-update-manifest.json
```


