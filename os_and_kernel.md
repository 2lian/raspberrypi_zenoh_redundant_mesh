# OS

I used `Raspberry PI OS lite`. Installed on a SD card with rpi imager. 
This repo should however work with most debian OS (rpiOS lite is just a very minimal Debian).

## Setup account and SSH (optional)

For some reason, my imager doesn't create an account, password and ssh. Maybe yours work.

### Enabling ssh, setting account, password and hostname:

Plug the pi's sd card on your PC and create an empty `ssh` file into the boot directory.

```bash
cd /media/USER_GOES_HERE/bootfs
touch ssh
```

Then in the same directory, create password hash, copy, then assign it to an user.

```bash
openssl passwd -6 <password here>
# copy the hash ouput below
echo 'USER_GOES_HERE:HASH_GOES_HERE' > userconf.txt
```

ssh should work from now on!

Start the pi and ssh onto it to change the hostname (default is `raspberrypi`).

```
sudo hostnamectl set-hostname HOSTNAME_GOES_HERE
```

Also change it on the network adapter

```
sudo nano /etc/hosts
```

# Kernel (linux 6.18)

The new kernel is required for driver enabling WiFi7 using the intel BE200.

The following will build the raspi kernel, this is not a generic x86 linux kernel. 
Procedure for generic kernel is similar if not easier (especially using `mainline` kernels).

### Prepare

Follow [this tutorial](https://www.raspberrypi.com/documentation/computers/linux_kernel.html) stopping before `make -j6 Image.gz modules dtbs`

### Change `.config`

Open `.config` and find the line with `CONFIG_IWLMLD`. Replace this line with `CONFIG_IWLMLD=m` to enable support for the most recent intel drivers.

### Compile

Continue [this tutorial](https://www.raspberrypi.com/documentation/computers/linux_kernel.html) . Run `make -j6 Image.gz modules dtbs` and after until reboot.

# Firmware

The firmware for the be200 is not included in the kernel, we need to download it.

```bash
cd /tmp
wget https://git.kernel.org/pub/scm/linux/kernel/git/firmware/linux-firmware.git/plain/intel/iwlwifi/iwlwifi-gl-c0-fm-c0-{90,92,94,96,97,98,100,101}.ucode

sudo cp iwlwifi-gl-c0-fm-c0-*.ucode /lib/firmware/
sudo chmod 644 /lib/firmware/iwlwifi-gl-c0-fm-c0-*.ucode
```

# WPA supplicant update

WPA supplicant handles WiFi implementation, login, security ... This is often not shipped with WiFi7 or MLO enabled.

```bash
git clone https://github.com/2lian/raspberrypi_zenoh_redundant_mesh.git ~/raspberrypi_zenoh_redundant_mesh

sudo apt install build-essential git pkg-config libssl-dev libnl-3-dev libnl-genl-3-dev libdbus-1-dev iw libnl-route-3-dev
git clone https://git.w1.fi/hostap.git ~/hostap || true

case "$(uname -m)" in
    aarch64)
        export PKG_CONFIG_PATH="$PKG_CONFIG_PATH:/usr/lib/aarch64-linux-gnu/pkgconfig/"
        ;;
    x86_64)
        export PKG_CONFIG_PATH="$PKG_CONFIG_PATH:/usr/lib/x86_64-linux-gnu/pkgconfig/"
        ;;
esac

cd ~/hostap
cd wpa_supplicant/
cp ~/raspberrypi_zenoh_redundant_mesh/wpa_config .config
make clean
make -j$(nproc)
sudo cp /sbin/wpa_supplicant /sbin/wpa_supplicant.bak
sudo cp -f wpa_supplicant /sbin/
wpa_supplicant -v
```

# Testing if it works

```bash
iw dev # lists all interfaces and their state
iw phy phy0 info # display info of the phy0 interface.
# Info to look for:
# - 6GHz bands on wifi6e+wifi7
# - "IBSS" for (potential) IBSS mesh mode support
# - "mesh point" for 801.11s mesh mode support

sudo wpa_cli -i wlan0 scan # scans all frequencies
sudo wpa_cli -i wlan0 scan_result # shows result (after a few seconds)
sudo nmcli dev wifi connect SSID password PASSWORD ifname wlan0 # connects to a station
sudo wpa_cli -i wlan0 status # active connection properties

sudo wpa_cli -i wlan0 roam BSSID # roams to the specified BSSID
```
