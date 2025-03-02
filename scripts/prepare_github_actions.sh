#!/bin/bash
# Run these commands locally to prepare your repository for GitHub Actions

# 1. Make scripts executable
chmod +x scripts/*.sh scripts/*.py

# 2. Create necessary directories
mkdir -p config output logs

# 3. Create default configuration files (with placeholder values)
cat > config/config.json << EOL
{
  "api_key": "YOUR_API_KEY",
  "channels": ["UCupvZG-5ko_eiXAupbDfxWw"],
  "min_duration": 15,
  "days_back": 2,
  "max_results": 20,
  "output_dir": "./output/",
  "update_time": "08:00"
}
EOL

# 4. Create a README for GitHub secrets
cat > GITHUB_SECRETS.md << EOL
# GitHub Secrets Required

To run the workflow, add these secrets to your GitHub repository:

- \`YOUTUBE_API_KEY\`: Your YouTube Data API key
- \`CLIENT_SECRET\`: Content of your client_secret.json file
- \`TOKEN_JSON\`: Content of your token.json file
- \`PLAYLIST_ID\`: Your YouTube playlist ID

## How to add these secrets:

1. Go to your repository on GitHub
2. Click on "Settings" > "Secrets and variables" > "Actions"
3. Click "New repository secret" to add each secret
EOL

# 5. Commit these changes
git add .
git commit -m "Prepare repository for GitHub Actions"
git push