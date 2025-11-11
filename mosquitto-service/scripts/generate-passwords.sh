#!/bin/bash
# ============================================
# Mosquitto Password File Generator
# ============================================
# This script generates the password file for Mosquitto authentication
# Run this script to create/update user passwords

set -e

PASSWD_FILE="/mosquitto/config/passwd"
TEMP_FILE="/tmp/mosquitto_passwd"

echo "=== Mosquitto Password File Generator ==="
echo "Generating password file at: $PASSWD_FILE"

# Create empty password file
> "$TEMP_FILE"

# Function to add user with password from environment variable
add_user() {
    local username="$1"
    local env_var="$2"
    local password="${!env_var}"
    
    if [ -n "$password" ]; then
        echo "Adding user: $username"
        mosquitto_passwd -b "$TEMP_FILE" "$username" "$password"
    else
        echo "Warning: Password for user '$username' not found in environment variable '$env_var'"
    fi
}

# Add users from environment variables
add_user "admin" "MQTT_ADMIN_PASSWORD"
add_user "linkya-backend" "MQTT_BACKEND_PASSWORD"
add_user "linkya-monitor" "MQTT_MONITOR_PASSWORD"
add_user "guest" "MQTT_GUEST_PASSWORD"

# Add dynamic users from PRM list if provided
if [ -n "$MQTT_PRM_PASSWORDS" ]; then
    echo "Adding PRM-based users..."
    # Format: PRM1:password1,PRM2:password2,...
    IFS=',' read -ra PRM_ENTRIES <<< "$MQTT_PRM_PASSWORDS"
    for entry in "${PRM_ENTRIES[@]}"; do
        IFS=':' read -ra PRM_DATA <<< "$entry"
        if [ ${#PRM_DATA[@]} -eq 2 ]; then
            prm="${PRM_DATA[0]}"
            password="${PRM_DATA[1]}"
            echo "Adding PRM user: $prm"
            mosquitto_passwd -b "$TEMP_FILE" "$prm" "$password"
            # Also add linkya-client-PRM pattern
            echo "Adding client user: linkya-client-$prm"
            mosquitto_passwd -b "$TEMP_FILE" "linkya-client-$prm" "$password"
        fi
    done
fi

# Move temp file to final location
mv "$TEMP_FILE" "$PASSWD_FILE"

# Set appropriate permissions
chmod 644 "$PASSWD_FILE"

echo "Password file generated successfully!"
echo "Users created:"
if [ -f "$PASSWD_FILE" ]; then
    grep -o '^[^:]*' "$PASSWD_FILE" | while read -r user; do
        echo "  - $user"
    done
fi