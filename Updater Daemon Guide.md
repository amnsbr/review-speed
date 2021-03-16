1. Install supervisor:

```
sudo apt install supervisor
```

2. Create 'review-speed.conf' in /etc/supervisor/conf.d with the following content:

```
[program:review-speed-updater]
command=/bin/bash -c 'source /var/www/review-speed/venv/bin/activate && python /var/www/review-speed/updater.py'
directory=/var/www/review-speed
user=<your_username>
numprocs=1
autostart=true
autorestart=true
startsecs=10
```

3. Run supervisor:

```
sudo supervisorctl reread
sudo supervisorctl update
```
4. Check if it's running:

```
sudo supervisorctl reread
```