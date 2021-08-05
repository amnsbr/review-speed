1. Copy the updater service file to systemd folder (will run the updater every 10 days)
```
sudo cp review_speed_updater.service /etc/systemd/system
```

2. Start and enable the service:

```
sudo systemctl start review_speed_updater
sudo systemctl enable review_speed_updater
```
3. Check if it's running:

```
sudo systemctl status review_speed_updater
```