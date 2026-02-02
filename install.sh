#!/bin/bash

# Script to install ADB and Scrcpy on Railway

echo "🔧 Installing system dependencies..."

# Update package manager
apt-get update

# Install ADB
echo "📱 Installing Android Debug Bridge (ADB)..."
apt-get install -y android-tools-adb android-tools-fastboot

# Install Scrcpy
echo "🎮 Installing Scrcpy..."
apt-get install -y scrcpy

# Install other dependencies
echo "📦 Installing additional dependencies..."
apt-get install -y \
    git \
    wget \
    unzip \
    openjdk-11-jdk \
    libusb1.0-0 \
    libusb-dev

# Clean up
apt-get clean && rm -rf /var/lib/apt/lists/*

# Verify installations
echo ""
echo "✅ Verifying installations..."
echo "ADB version:"
adb --version
echo ""
echo "Scrcpy version:"
scrcpy --version
echo ""
echo "✅ All dependencies installed successfully!"
