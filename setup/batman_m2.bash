set -oeu pipefail

export W7_CARD=wlan1
export BAT_CARD=wlan2
export BAT_IP=12
sudo ip link set $BAT_CARD down
sudo iw dev $BAT_CARD set type mp
sudo ip link set $BAT_CARD up

sudo iw dev $BAT_CARD mesh join mesh0 freq 2412

sudo iw dev $W7_CARD set power_save off
sudo iw dev $BAT_CARD set power_save off

sudo batctl if add $BAT_CARD
sudo batctl if add $W7_CARD
sudo ip link set up dev bat0

sudo ip addr add 10.42.42.$BAT_IP/24 dev bat0

watch sudo batctl n
