set -oeu pipefail

export LAN_CARD=wlan1
export BAT_IP=02

sudo batctl if add $LAN_CARD
sudo ip link set up dev bat0

sudo ip addr add 10.42.42.$BAT_IP/24 dev bat0

watch sudo batctl n

