# AO3-jellyfin-downloader
To download AO3 for Jellyfin

Honestly just a quick project so my partner can download AO3 before we go travelling with my portable media server running on the RPi4 - This is not polished or heavily maintained but it does work. 

```
services:
  ao3-downloader:
    build: .
    container_name: ao3-downloader
    network_mode: "host"
    privileged: true
    environment:
      - SAVE_FOLDER=/app/books
      - JELLYFIN_URL=http://localhost:8096
      - JELLYFIN_API_KEY=your_api_key
      - WIFI_SSID=wifi_if_running_on_wifi
    volumes:
      - /Jellyfin/Books:/app/books
      - /var/run/dbus/system_bus_socket:/var/run/dbus/system_bus_socket
    restart: unless-stopped
```

## Instructions to run

Make sure you have git and docker installed.

```git clone https://github.com/alyssaholland99/ao3-jellyfin-downloader.git```

Build and start the container

```docker compose up -d --build```

Then go to http://localhost:5000 (or if running remotely replace `localhost` with your machine IP)

## Environment Variables

| Environment Variable | Description |
| -------- | -------- |
| SAVE_FOLDER   | Container file path, you don't usually need to change this     |
| JELLYFIN_URL    | URL of your Jellyfin instance so it can run a library scan     |
| JELLYFIN_API_KEY    | API key from your Jellyfin instance     |
| WIFI_SSID    | If running with spotty WiFi connection, it will try connect to this network before downloading when 1.1.1.1 cannot be accessed

Change your volume `/Jellyfin/Books` to where your Jellyfin server stores books, otherwise this won't work at all. 


## LLM Disclosure

I used AI on this quick project, but I did review all the generated code to ensure that there wasn't anything actually malicous or awful. 

If you notice any issues, please raise an issue and I'll get to it ASAP