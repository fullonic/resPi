1 - Log in into pi
 run :
 sudo su -c "wpa_supplicant -B -i wlan0 -c<(wpa_passphrase "net" Girona2019) && dhclient wlan0"
