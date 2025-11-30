#!/bin/bash

echo "=================================="
echo "GitHub Repository Setup Script"
echo "=================================="
echo ""

# Repository name
REPO_NAME="tradelayout-backtesting-engine"

echo "Step 1: Login to GitHub"
echo "----------------------"
echo "Running: gh auth login"
gh auth login

if [ $? -ne 0 ]; then
    echo "❌ GitHub login failed. Please try again."
    exit 1
fi

echo ""
echo "Step 2: Create GitHub Repository"
echo "--------------------------------"
echo "Repository name: $REPO_NAME"
echo "Description: Complete backtesting engine for options trading with centralized tick processing"
echo ""

gh repo create $REPO_NAME \
    --public \
    --description "Complete backtesting engine for options trading with centralized tick processing, multi-timeframe analysis, and real-time P&L tracking" \
    --source=. \
    --remote=origin \
    --push

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ SUCCESS! Repository created and code pushed to GitHub"
    echo ""
    echo "Your repository is available at:"
    gh repo view --web
else
    echo ""
    echo "❌ Failed to create repository. Trying alternative method..."
    echo ""
    
    # Alternative: Create repo first, then push
    gh repo create $REPO_NAME \
        --public \
        --description "Complete backtesting engine for options trading"
    
    if [ $? -eq 0 ]; then
        # Get the GitHub username
        GH_USER=$(gh api user -q .login)
        
        echo "Adding remote..."
        git remote add origin https://github.com/$GH_USER/$REPO_NAME.git
        
        echo "Pushing code..."
        git push -u origin main
        
        echo ""
        echo "✅ Repository created and pushed successfully!"
        echo "Repository: https://github.com/$GH_USER/$REPO_NAME"
    else
        echo "❌ Failed to create repository. Please try manually:"
        echo "1. Go to https://github.com/new"
        echo "2. Create a repository named: $REPO_NAME"
        echo "3. Then run:"
        echo "   git remote add origin https://github.com/YOUR_USERNAME/$REPO_NAME.git"
        echo "   git push -u origin main"
    fi
fi
