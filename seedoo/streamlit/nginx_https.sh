#!/bin/bash

# Get the username of the user who originally logged in
ORIGINAL_USER=$(logname)

# Get the home directory of the originally logged-in user
HOME_DIR=$(getent passwd "$ORIGINAL_USER" | cut -d: -f6)

# User-defined variables for SSL certificate and key paths, using the determined home directory
SSL_CERT_PATH="$HOME_DIR/your_crt.crt"
SSL_KEY_PATH="$HOME_DIR/your_key.key"

# Check if the SSL certificate and key files exist
if [[ ! -f "$SSL_CERT_PATH" || ! -f "$SSL_KEY_PATH" ]]; then
    echo "Warning: SSL certificate or key file not found. Creating temporary ones for testing."

    # Create a temporary SSL certificate and key
    openssl req -x509 -newkey rsa:4096 -keyout "$HOME_DIR/temp_server.key" -out "$HOME_DIR/temp_app_seedoo_co.crt" -days 1 -nodes -subj "/CN=localhost"

    # Update paths to use the temporary files
    SSL_CERT_PATH="$HOME_DIR/temp_app_seedoo_co.crt"
    SSL_KEY_PATH="$HOME_DIR/temp_server.key"
fi

# Output paths for debugging
echo "Using SSL Certificate at: $SSL_CERT_PATH"
echo "Using SSL Key at: $SSL_KEY_PATH"


# Remove previous configurations
sudo rm -rf /etc/nginx/sites-enabled/streamlit
sudo rm -rf /etc/nginx/sites-available/streamlit

# Check if nginx is installed
if ! command -v nginx &> /dev/null
then
    echo "NGINX is not installed. Installing now..."
    sudo apt-get update
    apt-get install apache2-utils
    sudo apt-get install -y nginx nginx-extras
else
    echo "NGINX is already installed."
fi

# User-defined variables
USERNAME="your_user"
PASSWORD="your_password"

# Ensure nginx directory exists
if [ ! -d "/etc/nginx" ]; then
  sudo mkdir -p /etc/nginx
fi

# Set up authentication
#echo "Setting up authentication..."
sudo htpasswd -cb /etc/nginx/.htpasswd $USERNAME $PASSWORD
#ADD ANOTHER USER
sudo htpasswd -b /etc/nginx/.htpasswd 'gal' '&d&#HKXcer3$TmKN'

# Configure nginx
echo "Configuring nginx..."

# Configure nginx for Streamlit
cat << EOF | sudo tee /etc/nginx/sites-available/streamlit
# HTTP to HTTPS redirection
server {
    listen 80;
    server_name app.seedoo.co;
    return 301 https://\$host\$request_uri;
}

# Server block for port 443 (HTTPS and WebSocket)
server {
    listen 443 ssl;
    server_name app.seedoo.co;

    ssl_certificate $SSL_CERT_PATH;
    ssl_certificate_key $SSL_KEY_PATH;

    location /images/ {
        satisfy any;
        auth_basic "Restricted Content";
        auth_basic_user_file /etc/nginx/.htpasswd;

        expires 1d;
        add_header Set-Cookie "authed=true; Path=/; HttpOnly";

        # Forward image requests to the Python server
        proxy_pass http://127.0.0.1:8000;

    }

    location /static_data/ {
        satisfy any;
        auth_basic "Restricted Content";
        auth_basic_user_file /etc/nginx/.htpasswd;

        alias /seedoodata/datasets/data/;
        # Optional: Adding cache control headers
        expires 1d;

        # Set cookie after successful authentication
        add_header Set-Cookie "authed=true; Path=/; HttpOnly";
    }

    location / {
        satisfy any;

        allow 18.200.72.106/32;
        allow 52.50.0.91/32;
        allow 52.241.231.53/32;
        deny all;
        client_max_body_size 10M;


        proxy_pass http://127.0.0.1:8501;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme; # Added to maintain security context
        proxy_http_version 1.1; # Ensure HTTP/1.1 for WebSockets
        proxy_set_header Upgrade \$http_upgrade; # Handle WebSocket upgrades
        proxy_set_header Connection "upgrade"; # Maintain persistent connections


        # Basic Authentication
        auth_basic \$auth_type;
        auth_basic_user_file /etc/nginx/.htpasswd;

        # Set cookie after successful authentication
        add_header Set-Cookie "authed=true; Path=/; HttpOnly";

          # Enhanced buffer settings
        proxy_buffers 8 32k;
        proxy_buffer_size 64k;

    }

    location /ws {

        satisfy any;
        client_max_body_size 10M;
        allow 18.200.72.106/32;
        allow 52.50.0.91/32;
        allow 52.241.231.53/32;
        deny all;

        proxy_pass http://127.0.0.1:9897;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;

        # Basic Authentication
        auth_basic \$auth_type;
        auth_basic_user_file /etc/nginx/.htpasswd;
    }

   location /_stcore/stream {
        satisfy any;

        allow 18.200.72.106/32;
        allow 52.50.0.91/32;
        allow 52.241.231.53/32;
        deny all;

        proxy_pass http://127.0.0.1:8501/_stcore/stream;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;

        # Basic Authentication
        auth_basic \$auth_type;
        auth_basic_user_file /etc/nginx/.htpasswd;

        # Enhanced buffer settings
        proxy_buffers 8 32k;
        proxy_buffer_size 64k;

    }

    # Enable gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

    # Cache JavaScript files
    location ~* \.(js|tsx|css|html)(\.gz)$ {
        expires 3d;
        add_header Cache-Control "public, no-transform";
        etag on;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/streamlit /etc/nginx/sites-enabled



# Restart nginx to apply the changes
sudo systemctl restart nginx

sudo chown www-data:www-data /etc/nginx/.htpasswd
sudo chown -R www-data:www-data /etc/nginx/conf.d/