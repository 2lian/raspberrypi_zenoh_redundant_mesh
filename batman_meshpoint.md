# Setting up BATMAN with Mesh Point (`801.11s`)

Set the Wi-Fi interface you want to work with using `export WIFI_CARD=<your card here>`. List your interfaces with `iw dev`

## Disable previous Wi-Fi connection and managers

```bash
sudo nano /etc/NetworkManager/conf.d/99-unmanaged-$WIFI_CARD.conf
# write this
######################################
[keyfile]
unmanaged-devices=interface-name:$WIFI_CARD
# REPLACE $WIFI_CARD manually here !!!!!
######################################

sudo systemctl restart NetworkManager
sudo pkill -f "wpa_supplicant.*$WIFI_CARD" # maybe necessary
```

### Connect/create a Mesh Point (`801.11s`) peer-to-peer Wi-Fi network

```bash
sudo ip link set $WIFI_CARD down
sudo iw dev $WIFI_CARD set type mp
sudo ip link set $WIFI_CARD up
```

Setup your config in `/etc/wpa_supplicant/mesh.conf`, you can copy the one in this repo with:

```bash
sudo cp ~/raspberrypi_zenoh_redundant_mesh/wpa_supplicant.conf /etc/wpa_supplicant/mesh.conf
```

Use wpa_supplicant to start the mesh.

```bash
sudo wpa_supplicant -D nl80211 -i $WIFI_CARD -c /etc/wpa_supplicant/mesh.conf -B
```

## Setup the BATMAN routing protocol

`bat0` will be your BATMAN network, exposed as a standard IP routing network.

```bash
sudo apt install batctl
sudo batctl if add $WIFI_CARD
sudo ip link set up dev bat0
```

See other client and neighbors using:

```bash
iw dev $WIFI_CARD station dump  # shows WiFi neighbors and more
sudo batctl n  # shows batman neighbors
sudo batctl o  # shows the originator table (routing)
```

### Give yourself an IP address

```bash
sudo ip addr add 10.42.42.<YOUR_IP>/24 dev bat0
```

# Revert changes

```bash
sudo ip link set down dev bat0
sudo batctl if del $WIFI_CARD
sudo ip link set $WIFI_CARD down
sudo iw dev $WIFI_CARD set type managed
sudo ip link set $WIFI_CARD up
```

Let NetworkManager use the card again
```bash
sudo rm /etc/NetworkManager/conf.d/99-unmanaged-$WIFI_CARD.conf
```
