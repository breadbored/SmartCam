#!/usr/bin/env python3
"""
Smart Cam Controller CLI

by BreadCodes
"""

import argparse
import json
import time
from typing import Any

from smartcam import SmartCameraAPI, get_timezone_id


def print_json(data: Any):
    if data:
        print(json.dumps(data, indent=2))


def interactive_menu(api: SmartCameraAPI):
    def show_streams():
        print("\nAvailable RTSP Stream URLs:")
        print("-" * 80)
        for profile in api.get_stream_profiles():
            url = api.get_rtsp_url(profile["id"])
            print(
                f"\nProfile {profile['id']}: {profile['resolution']} @ {profile['fps']}fps"
            )
            print(f"  URL: {url}")
            print(f'  VLC: vlc "{url}"')
            print(f'  ffplay: ffplay -rtsp_transport tcp -i "{url}"')
        print()

    def restart_camera(api):
        confirm = input("Are you sure you want to restart the camera? (yes/no): ")
        if confirm.lower() == "yes":
            print_json(api.perform_restart())
            print("Camera is restarting...")
        else:
            print("Cancelled.")

    def factory_reset(api):
        print("\nWARNING: Factory reset will erase all settings!")
        confirm = input("Type 'RESET' to confirm factory reset: ")
        if confirm == "RESET":
            print_json(api.perform_factory_reset())
            print("Factory reset initiated...")
        else:
            print("Cancelled.")

    def set_wifi(api):
        """Interactive WiFi setup - mirrors bash script functionality"""
        # Get current WiFi state
        current = api.get_wifi()
        if not current:
            print("Failed to get WiFi status")
            return

        current_state = current.get("Enable", False)
        print(f"Current WiFi State: {'Enabled' if current_state else 'Disabled'}")

        if current_state:
            # WiFi is enabled
            connected_ssid = current.get("ConnectedSSID")

            if connected_ssid and connected_ssid != "null":
                print(f"\nCurrently connected to WiFi SSID: {connected_ssid}")
                change = input(
                    "Do you want to change the WiFi network? (Y/N): "
                ).strip()
                if not change.upper().startswith("Y"):
                    # Ask to disable or skip
                    action = input(
                        "WiFi is ON. [D]isable or [S]kip setup? (D/S): "
                    ).strip()
                    if action.upper().startswith("D"):
                        # Check for ethernet before disabling
                        iface = api.get_interface()
                        if iface:
                            broadcast = iface.get("BroadcastAddress", "")
                            # Calculate expected broadcast
                            ip_parts = api.ip.split(".")
                            expected_broadcast = (
                                f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.255"
                            )

                            if broadcast != expected_broadcast:
                                print(
                                    "\nTo deactivate WiFi, connect your ethernet cable to the camera!"
                                )
                                wait = input(
                                    "Connect cable and press [Enter] to retry or [Q] to cancel: "
                                ).strip()
                                if wait.upper().startswith("Q"):
                                    print("Action canceled.")
                                    return

                                # Recheck interface
                                iface = api.get_interface()
                                if iface:
                                    broadcast = iface.get("BroadcastAddress", "")
                                    if broadcast != expected_broadcast:
                                        print(
                                            "Couldn't detect cable. You can't deactivate WiFi!"
                                        )
                                        return

                        api.set_wifi_enabled(False)
                        print("WiFi disabled.")
                    else:
                        print("Operation skipped.")
                    return

            # WiFi enabled but not connected or user wants to change
            action = input("WiFi is ON. [D]isable or [S]et up/Connect? (D/S): ").strip()
            if action.upper().startswith("D"):
                # Check for ethernet before disabling
                iface = api.get_interface()
                if iface:
                    broadcast = iface.get("BroadcastAddress", "")
                    ip_parts = api.ip.split(".")
                    expected_broadcast = (
                        f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.255"
                    )

                    if broadcast != expected_broadcast:
                        print(
                            "\nTo deactivate WiFi, connect your ethernet cable to the camera!"
                        )
                        wait = input(
                            "Connect cable and press [Enter] to retry or [Q] to cancel: "
                        ).strip()
                        if wait.upper().startswith("Q"):
                            print("Operation skipped.")
                            return

                        # Recheck interface
                        iface = api.get_interface()
                        if iface:
                            broadcast = iface.get("BroadcastAddress", "")
                            if broadcast != expected_broadcast:
                                print(
                                    "Couldn't detect cable. You can't deactivate WiFi!"
                                )
                                return

                api.set_wifi_enabled(False)
                print("WiFi disabled.")
                return
            elif not action.upper().startswith("S"):
                print("Operation cancelled.")
                return
        else:
            # WiFi is disabled
            confirm = input("WiFi is OFF. Enable and set up? (Y/N): ").strip()
            if confirm.upper().startswith("Y"):
                api.set_wifi_enabled(True)
                print("WiFi enabled.")

                # Check if already configured
                wifi_status = api.get_wifi()
                if wifi_status:
                    connected_ssid = wifi_status.get("ConnectedSSID")
                    if connected_ssid and connected_ssid != "null":
                        print(
                            f"SSID already configured: {connected_ssid}. Attempting to connect..."
                        )
                        psk = input(
                            f"Enter WiFi password for {connected_ssid}: "
                        ).strip()

                        api.connect_wifi(connected_ssid, psk)
                        print(f"Attempted to connect to {connected_ssid}")
                        return
            else:
                print("Operation cancelled.")
                return

        # Set up new WiFi connection
        scan_choice = input(
            "Scan for networks (S) or enter SSID manually (M)? "
        ).strip()

        ssid = None
        if scan_choice.upper().startswith("S"):
            scan_result = api.scan_wifi()
            if scan_result:
                # Extract available networks
                networks = []
                for i in range(10):  # Check up to 10 networks
                    key = f"AvailableNetworks.{i}.SSID"
                    if key in scan_result and scan_result[key]:
                        networks.append(scan_result[key])

                if not networks:
                    print("No networks found.")
                    manual = input("Enter SSID manually? (Y/N): ").strip()
                    if manual.upper().startswith("Y"):
                        ssid = input("Enter SSID: ").strip()
                    else:
                        print("Operation cancelled.")
                        return
                else:
                    print("\nAvailable Networks:")
                    for i, net in enumerate(networks, 1):
                        print(f"{i}. {net}")

                    sel = input(
                        "\nSelect network number or press [M] to enter SSID manually: "
                    ).strip()
                    if sel.isdigit() and 1 <= int(sel) <= len(networks):
                        ssid = networks[int(sel) - 1]
                    elif sel.upper().startswith("M"):
                        ssid = input("Enter SSID: ").strip()
                    else:
                        print("Operation cancelled.")
                        return
            else:
                print("Scan failed.")
                return
        else:
            ssid = input("Enter SSID: ").strip()

        if not ssid:
            print("No SSID provided.")
            return

        psk = input("Enter WiFi password: ").strip()

        # Connect to WiFi
        api.connect_wifi(ssid, psk)
        print(f"Attempted to connect to {ssid}")

        # Give it a moment to connect
        time.sleep(2)

        # Verify connection
        wifi_status = api.get_wifi()
        if wifi_status:
            connected_ssid = wifi_status.get("ConnectedSSID")

            if connected_ssid == ssid:
                print(f"\nConnected to WiFi SSID: {ssid}")

                # Check interface
                iface = api.get_interface()
                if iface:
                    broadcast = iface.get("BroadcastAddress", "")
                    ip_parts = api.ip.split(".")
                    expected_broadcast = (
                        f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.255"
                    )

                    if broadcast == "127.0.0.1":
                        print(
                            "Camera is connected via WiFi (no Ethernet cable detected)."
                        )
                    elif broadcast == expected_broadcast:
                        print("Camera is still connected via Ethernet cable.")
                        disc = input(
                            "Disconnect Ethernet and press [Enter] to recheck, or [Q] to abort: "
                        ).strip()
                        if not disc.upper().startswith("Q"):
                            iface = api.get_interface()
                            if iface:
                                broadcast = iface.get("BroadcastAddress", "")
                                if broadcast == "127.0.0.1":
                                    print("Now connected via WiFi only!")
                                else:
                                    print(
                                        "Still not connected via WiFi only. Please check connections."
                                    )
                        else:
                            print("Operation cancelled.")
                    else:
                        print(f"Unknown network state. BroadcastAddress: {broadcast}")
            else:
                print(
                    f"Not connected to the selected SSID ({ssid}). Please check WiFi credentials or signal."
                )

    def set_timezone(api):
        print("\nCurrent date/time settings:")
        print_json(api.get_date())

        timezone = input(
            "\nTimezone (location, UTC offset, or timezone ID, blank to keep current): "
        ).strip()

        dst = input(
            "Daylight saving time [y/n, blank to keep current]: "
        ).strip().lower()

        timezone_id = None
        if timezone:
            timezone_id = get_timezone_id(api.timezones, timezone)

        if dst in ("y", "yes"):
            dst_enable = True
        elif dst in ("n", "no"):
            dst_enable = False
        elif not dst:
            dst_enable = None
        else:
            raise ValueError("DST must be y, n, or blank")

        if timezone_id is None and dst_enable is None:
            return
        api.set_timezone(timezone_id, dst_enable)

    operations = [
        ("Get Device Info", lambda: print_json(api.get_device_info())),
        ("Get Date/Time", lambda: print_json(api.get_date())),
        ("Get Timezone List", lambda: print_json(api.get_timezone_list()["TimeZoneList"])),
        ("Set Timezone (Interactive)", lambda: set_timezone(api)),
        ("Get Network Interface", lambda: print_json(api.get_interface())),
        ("Get WiFi Status", lambda: print_json(api.get_wifi())),
        ("Scan WiFi Networks", lambda: print_json(api.scan_wifi())),
        ("Get Camera Settings", lambda: print_json(api.get_camera())),
        ("Get Image Enhancements", lambda: print_json(api.get_image_enhancements())),
        ("Get Flip Settings", lambda: print_json(api.get_flip())),
        ("Get Overlay Settings", lambda: print_json(api.get_overlay())),
        ("Get LED Status", lambda: print_json(api.get_other_outputs())),
        ("Get Audio Input", lambda: print_json(api.get_audio_input())),
        ("Get Audio Output", lambda: print_json(api.get_audio_output())),
        ("Get Video Analysis", lambda: print_json(api.get_video_analysis())),
        ("Get Audio Detection", lambda: print_json(api.get_audio_detection())),
        ("Get Alarm Settings", lambda: print_json(api.get_alarm())),
        ("Get Alarm Input", lambda: print_json(api.get_alarm_input())),
        ("Get Alarm Output", lambda: print_json(api.get_alarm_output())),
        ("Enable Vertical Flip", lambda: print_json(api.set_vertical_flip(True))),
        ("Disable Vertical Flip", lambda: print_json(api.set_vertical_flip(False))),
        ("Enable Horizontal Flip", lambda: print_json(api.set_horizontal_flip(True))),
        ("Disable Horizontal Flip", lambda: print_json(api.set_horizontal_flip(False))),
        ("Enable Time Overlay", lambda: print_json(api.set_overlay(True))),
        ("Disable Time Overlay", lambda: print_json(api.set_overlay(False))),
        ("Turn LED On", lambda: print_json(api.set_status_led("On"))),
        ("Turn LED Off", lambda: print_json(api.set_status_led("Off"))),
        (
            "Enable Motion Detection",
            lambda: print_json(api.set_detection_type("MotionDetection")),
        ),
        ("Disable Motion Detection", lambda: print_json(api.set_detection_type("Off"))),
        ("Enable WiFi", lambda: print_json(api.set_wifi_enabled(True))),
        ("Disable WiFi", lambda: print_json(api.set_wifi_enabled(False))),
        ("Set WiFi (Interactive)", lambda: set_wifi(api)),
        ("Show RTSP Stream URLs", show_streams),
        ("Restart Camera", lambda: restart_camera(api)),
        ("Factory Reset", lambda: factory_reset(api)),
    ]

    while True:
        print("\n" + "=" * 80)
        print("Samsung Smart Cam Controller - Interactive Menu")
        print("=" * 80)
        print()

        mid = (len(operations) + 1) // 2
        for i in range(mid):
            left_idx = i
            right_idx = i + mid

            left = f"{left_idx + 1:2d}. {operations[left_idx][0]}"
            print(f"{left:40s}", end="")

            if right_idx < len(operations):
                right = f"{right_idx + 1:2d}. {operations[right_idx][0]}"
                print(right)
            else:
                print()

        print(f"\n{len(operations) + 1:2d}. Exit")
        print()

        try:
            choice = input("Enter option number: ").strip()

            if not choice:
                continue

            choice_num = int(choice)

            if choice_num == len(operations) + 1:
                print("Goodbye!")
                break

            if 1 <= choice_num <= len(operations):
                print()
                operations[choice_num - 1][1]()
                input("\nPress Enter to continue...")
            else:
                print("Invalid choice.")

        except ValueError:
            print("Invalid input. Please enter a number.")
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")
            input("\nPress Enter to continue...")


def main():
    parser = argparse.ArgumentParser(
        description="SmartCam Controller - Control Samsung SmartCam cameras"
    )
    parser.add_argument(
        "--ip",
        default="192.168.1.200",
        help="Camera IP address (default: 192.168.1.200)",
    )
    parser.add_argument("--username", default="admin", help="Username (default: admin)")
    parser.add_argument("--password", help="Password (will prompt if not provided)")

    parser.add_argument("--info", action="store_true", help="Get device info")
    parser.add_argument("--wifi", action="store_true", help="Get WiFi status")
    parser.add_argument("--scan", action="store_true", help="Scan WiFi networks")
    parser.add_argument("--streams", action="store_true", help="Show RTSP stream URLs")
    parser.add_argument("--led-on", action="store_true", help="Turn status LED on")
    parser.add_argument("--led-off", action="store_true", help="Turn status LED off")
    parser.add_argument("--flip-v", action="store_true", help="Toggle vertical flip")
    parser.add_argument("--flip-h", action="store_true", help="Toggle horizontal flip")
    parser.add_argument(
        "--timezone",
        default=None,
        help="Set timezone by location, UTC offset, or timezone ID.",
    )
    parser.add_argument(
        "--dst",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable or disable daylight saving time.",
    )

    args = parser.parse_args()

    if not args.password:
        from getpass import getpass

        password = getpass(f"Enter password for {args.username}@{args.ip}: ")
    else:
        password = args.password

    api = SmartCameraAPI(args.ip, args.username, password)

    has_action = any(
        (
            args.info,
            args.wifi,
            args.scan,
            args.streams,
            args.led_on,
            args.led_off,
            args.flip_v,
            args.flip_h,
            args.timezone is not None,
            args.dst is not None,
        )
    )

    if args.info:
        print_json(api.get_device_info())

    if args.wifi:
        print_json(api.get_wifi())

    if args.scan:
        print_json(api.scan_wifi())

    if args.streams:
        print("\nAvailable RTSP Stream URLs:")
        print("-" * 80)
        for profile in api.get_stream_profiles():
            url = api.get_rtsp_url(profile["id"])
            print(
                f"\nProfile {profile['id']}: {profile['resolution']} @ {profile['fps']}fps"
            )
            print(f"  URL: {url}")
            print(f'  VLC: vlc "{url}"')
            print(f'  ffplay: ffplay -rtsp_transport tcp -i "{url}"')

    if args.led_on:
        print_json(api.set_status_led("On"))

    if args.led_off:
        print_json(api.set_status_led("Off"))

    if args.flip_v:
        current = api.get_flip()
        if current:
            enabled = current.get("VerticalFlipEnable", False)
            print_json(api.set_vertical_flip(not enabled))

    if args.flip_h:
        current = api.get_flip()
        if current:
            enabled = current.get("HorizontalFlipEnable", False)
            print_json(api.set_horizontal_flip(not enabled))

    if args.timezone is not None or args.dst is not None:
        timezone_id = (
            get_timezone_id(api.timezones, args.timezone)
            if args.timezone
            else None
        )
        print_json(api.set_timezone(timezone_id, args.dst))

    if not has_action:
        interactive_menu(api)


if __name__ == "__main__":
    main()
