#!/bin/bash
# TinTown Bridge Monitor Script
# Usage: ./monitor_bridge.sh [option]

show_help() {
    echo "🎯 TinTown Bridge Monitoring Commands"
    echo "======================================"
    echo ""
    echo "Real-time monitoring (recommended):"
    echo "  sudo journalctl -u tintown-bridge.service -f"
    echo ""
    echo "Complete console log (includes ALL events):"
    echo "  tail -f ~/projects/TinTown/logs/console/bridge_console_*.log"
    echo ""
    echo "View recent systemd logs:"
    echo "  sudo journalctl -u tintown-bridge.service -n 50 --no-pager"
    echo ""
    echo "Check service status:"
    echo "  sudo systemctl status tintown-bridge.service"
    echo ""
    echo "View today's systemd logs only:"
    echo "  sudo journalctl -u tintown-bridge.service --since today --no-pager"
    echo ""
    echo "View logs with timestamps:"
    echo "  sudo journalctl -u tintown-bridge.service -f --no-pager -o short-iso"
    echo ""
    echo "Restart bridge (when AMG timer powered on):"
    echo "  sudo systemctl restart tintown-bridge.service"
    echo ""
    echo "📝 NOTE: Console logs include AMG beeps and all events that systemd might filter"
}

case "$1" in
    "live"|"")
        echo "🎯 Starting real-time bridge monitoring... (Ctrl+C to exit)"
        echo "=================================================="
        sudo journalctl -u tintown-bridge.service -f --no-pager
        ;;
    "console")
        echo "🎯 Starting complete console log monitoring... (Ctrl+C to exit)"
        echo "📝 This shows ALL events including AMG beeps"
        echo "=================================================="
        tail -f ~/projects/TinTown/logs/console/bridge_console_*.log
        ;;
    "status")
        sudo systemctl status tintown-bridge.service
        ;;
    "recent")
        sudo journalctl -u tintown-bridge.service -n 50 --no-pager
        ;;
    "today")
        sudo journalctl -u tintown-bridge.service --since today --no-pager
        ;;
    "restart")
        echo "🔄 Restarting TinTown Bridge..."
        sudo systemctl restart tintown-bridge.service
        echo "✅ Bridge restarted. Monitoring startup..."
        sleep 2
        sudo journalctl -u tintown-bridge.service -f --no-pager -n 10
        ;;
    "help"|"-h"|"--help")
        show_help
        ;;
    *)
        echo "Unknown option: $1"
        show_help
        exit 1
        ;;
esac