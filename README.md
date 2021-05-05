# india-vaccine-bot

## Installation

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running

```
export WEBHOOK_URL=xxx
python3 bot.py
```

## Running under systemd

Add this service file to `/etc/systemd/system/vaxbot.service`

```
After=network.target
StartLimitIntervalSec=0

[Service]
Environment="WEBHOOK_URL=xxx"
Type=simple
Restart=always
RestartSec=1
User=ubuntu
ExecStart=/home/ubuntu/india-vaccine-bot/venv/bin/python3 /home/ubuntu/india-vaccine-bot/bot.py

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```
sudo systemctl enable vaxbot
sudo systemctl start vaxbot
```

Restart the service:

```
sudo service vaxbot restart
```

Watch the logs:
```
journalctl -u vaxbot.service -f
```
