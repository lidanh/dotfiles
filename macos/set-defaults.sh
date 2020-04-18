# Sets reasonable macOS defaults.
#
# Or, in other words, set shit how I like in macOS.
#
# The original idea (and a couple settings) were grabbed from:
#   https://github.com/mathiasbynens/dotfiles/blob/master/.macos
#
# Run ./set-defaults.sh and you'll be good to go.


# Set computer name (as done via System Preferences → Sharing)
sudo scutil --set ComputerName "Lidan-Macbook"
sudo scutil --set HostName "Lidan-Macbook"
sudo scutil --set LocalHostName "Lidan-Macbook"
sudo defaults write /Library/Preferences/SystemConfiguration/com.apple.smb.server NetBIOSName -string "Lidan-Macbook"


# ==============================================
# Files and folders
# ==============================================

# Show the ~/Library directory
chflags nohidden "${HOME}/Library"

# Don't show the ~/bin directory
chflags hidden "${HOME}/bin"


# ==============================================
# NSGlobalDomain settings
# ==============================================

defaults write com.apple.systemuiserver menuExtras -array "/System/Library/CoreServices/Menu Extras/Bluetooth.menu" "/System/Library/CoreServices/Menu Extras/Clock.menu" "/System/Library/CoreServices/Menu Extras/Displays.menu" "/System/Library/CoreServices/Menu Extras/Volume.menu"

# Locale
defaults write NSGlobalDomain AppleLocale -string "en_IL"
defaults write NSGlobalDomain AppleLanguages -array "en-IL" "he-IL"
defaults write NSGlobalDomain AppleMeasurementUnits -string "Centimeters"
defaults write NSGlobalDomain AppleMetricUnits -bool true
defaults delete com.apple.HIToolbox AppleEnabledInputSources
defaults write com.apple.HIToolbox AppleEnabledInputSources -array-add '<dict><key>InputSourceKind</key><string>Keyboard Layout</string><key>KeyboardLayout ID</key><integer>252</integer><key>KeyboardLayout Name</key><string>ABC</string></dict>'
defaults write com.apple.HIToolbox AppleEnabledInputSources -array-add '<dict><key>InputSourceKind</key><string>Keyboard Layout</string><key>KeyboardLayout ID</key><integer>-18432</integer><key>KeyboardLayout Name</key><string>Hebrew</string></dict>'

# enable on-screen keyboard and character viewers
defaults write com.apple.HIToolbox AppleEnabledInputSources -array-add '<dict><key>Bundle ID</key><string>com.apple.inputmethod.EmojiFunctionRowItem</string><key>InputSourceKind</key><string>Non Keyboard Input Method</string></dict>'
defaults write com.apple.HIToolbox AppleEnabledInputSources -array-add '<dict><key>Bundle ID</key><string>com.apple.CharacterPaletteIM</string><key>InputSourceKind</key><string>Non Keyboard Input Method</string></dict>'
defaults write com.apple.HIToolbox AppleEnabledInputSources -array-add '<dict><key>Bundle ID</key><string>com.apple.KeyboardViewer</string><key>InputSourceKind</key><string>Non Keyboard Input Method</string></dict>'

# Input Sources > Select previous source in Input menu : Cmd + Space
defaults write com.apple.symbolichotkeys.plist AppleSymbolicHotKeys -dict-add 60 "
  <dict>
    <key>enabled</key><true/>
    <key>value</key><dict>
      <key>type</key><string>standard</string>
      <key>parameters</key>
      <array>
        <integer>32</integer>
        <integer>49</integer>
        <integer>1048576</integer>
      </array>
    </dict>
  </dict>
"

defaults write com.apple.symbolichotkeys.plist AppleSymbolicHotKeys -dict-add 61 "
  <dict>
    <key>enabled</key><false/>
    <key>value</key><dict>
      <key>type</key><string>standard</string>
      <key>parameters</key>
      <array>
        <integer>32</integer>
        <integer>49</integer>
        <integer>786432</integer>
      </array>
    </dict>
  </dict>
"

# Spotlight > Show Spotlight search : Control + Space
defaults write com.apple.symbolichotkeys.plist AppleSymbolicHotKeys -dict-add 64 "
  <dict>
    <key>enabled</key><true/>
    <key>value</key><dict>
      <key>type</key><string>standard</string>
      <key>parameters</key>
      <array>
        <integer>32</integer>
        <integer>49</integer>
        <integer>262144</integer>
      </array>
    </dict>
  </dict>
"

# Switch keyboard f1,f2,...
defaults write NSGlobalDomain com.apple.keyboard.fnState -bool true

# Use smooth scrolling
defaults write NSGlobalDomain AppleScrollAnimationEnabled -bool true

# Enable key repeat
defaults write NSGlobalDomain ApplePressAndHoldEnabled -bool false

# Set keyboard repeat rate
defaults write NSGlobalDomain KeyRepeat -int 1

# Audio and sound effects

# Enable feedback when changing volume
defaults write NSGlobalDomain com.apple.sound.beep.feedback -bool true

# Automatically quit printer app once the print jobs complete
defaults write com.apple.print.PrintingPrefs "Quit When Finished" -bool true

# Expand save panel by default
defaults write NSGlobalDomain NSNavPanelExpandedStateForSaveMode -bool true
defaults write NSGlobalDomain NSNavPanelExpandedStateForSaveMode2 -bool true

# Expand print panel by default
defaults write NSGlobalDomain PMPrintingExpandedStateForPrint -bool true
defaults write NSGlobalDomain PMPrintingExpandedStateForPrint2 -bool true

# Menu bar: show remaining battery percentage
defaults write com.apple.menuextra.battery ShowPercent -string "YES"

# Enable dark mode (Mojave)
defaults write -g AppleInterfaceStyle -string "Dark"
# Exclude notification center from dark mode
defaults write com.apple.notificationcenterui NSRequiresAquaSystemAppearance -bool Yes
# Exclude spotlight from dark mode
defaults write com.apple.Spotlight NSRequiresAquaSystemAppearance -bool Yes
# Exclude finder from dark mode
defaults write com.apple.finder NSRequiresAquaSystemAppearance -bool Yes
# Exclude messages from dark mode
defaults write com.apple.iChat NSRequiresAquaSystemAppearance -bool Yes
# Exclude calendar from dark mode
defaults write com.apple.iCal NSRequiresAquaSystemAppearance -bool Yes
# Exclude activity monitor from dark mode
defaults write com.apple.ActivityMonitor NSRequiresAquaSystemAppearance -bool Yes
# Exclude app store from dark mode
defaults write com.apple.AppStore NSRequiresAquaSystemAppearance -bool Yes
# Exclude Xcode from dark mode
defaults write com.apple.dt.Xcode NSRequiresAquaSystemAppearance -bool Yes
# Exclude chrome from dark mode
defaults write com.google.Chrome NSRequiresAquaSystemAppearance -bool Yes
# Fix issue with Adobe apps
defaults delete -g NSRequiresAquaSystemAppearance

# ==============================================
# Mouse and trackpad
# ==============================================

# Tap to click
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad Clicking -bool true
defaults write com.apple.AppleMultitouchTrackpad Clicking -bool true
defaults -currentHost write NSGlobalDomain com.apple.mouse.tapBehavior -int 1
defaults write NSGlobalDomain com.apple.mouse.tapBehavior -int 1

# Tap with two fingers to emulate right click
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad TrackpadRightClick -bool true

# Disable "tap-and-a-half" to drag.
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad Dragging -int 0
defaults write com.apple.AppleMultitouchTrackpad Dragging -int 0

# Enable 3-finger drag. (Moving with 3 fingers in any window)
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad TrackpadThreeFingerDrag -bool true
defaults write com.apple.AppleMultitouchTrackpad TrackpadThreeFingerDrag -bool true

# Enable force click
defaults write NSGlobalDomain com.apple.trackpad.forceClick -bool true

# Silent clicking
defaults write com.apple.AppleMultitouchTrackpad ActuationStrength -int 0

# Tracking Speed
# 0: Slow
# 3: Fast
defaults write NSGlobalDomain com.apple.trackpad.scaling -float 1.5

# Zoom in or out
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad TrackpadPinch -bool true

# Smart zoom, double-tap with two fingers
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad TrackpadTwoFingerDoubleTapGesture -bool true

# Rotate
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad TrackpadRotate -bool true

# Notification Center
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad TrackpadTwoFingerFromRightEdgeSwipeGesture -int 3


# ==============================================
# Xcode
# ==============================================

# Always use spaces for indenting
defaults write com.apple.dt.Xcode DVTTextIndentUsingTabs -bool false

# Show tab bar
defaults write com.apple.dt.Xcode AlwaysShowTabBar -bool true


# ==============================================
# Finder
# ==============================================

# When performing a search, search the current folder by default
defaults write com.apple.finder FXDefaultSearchScope -string "SCcf"

# Avoid creating .DS_Store files on network volumes
defaults write com.apple.desktopservices DSDontWriteNetworkStores -bool true

# Set the Finder prefs for showing a few different volumes on the Desktop.
defaults write com.apple.finder ShowExternalHardDrivesOnDesktop -bool true
defaults write com.apple.finder ShowRemovableMediaOnDesktop -bool true

# Set HOME as the default location for new Finder windows
defaults write com.apple.finder NewWindowTarget -string "PfHm"
defaults write com.apple.finder NewWindowTargetPath -string "file://${HOME}/"

# ==============================================
# Safari & WebKit
# ==============================================

# Show status bar
defaults write com.apple.Safari ShowStatusBar -bool true

# Hide Safari's bookmark bar.
defaults write com.apple.Safari ShowFavoritesBar -bool true
defaults write com.apple.Safari "ShowFavoritesBar-v2" -bool true

# Set up Safari for development.
defaults write com.apple.Safari IncludeInternalDebugMenu -bool true
defaults write com.apple.Safari IncludeDevelopMenu -bool true
defaults write com.apple.Safari WebKitDeveloperExtrasEnabledPreferenceKey -bool true
defaults write com.apple.Safari "com.apple.Safari.ContentPageGroupIdentifier.WebKit2DeveloperExtrasEnabled" -bool true
defaults write NSGlobalDomain WebKitDeveloperExtras -bool true

# Tabs settings

# Open pages in tabs instead of windows: automatically
defaults write com.apple.Safari TabCreationPolicy -int 1

# Update extensions automatically
defaults write com.apple.Safari InstallExtensionUpdatesAutomatically -bool true


# Use AirDrop over every interface. srsly this should be a default.
defaults write com.apple.NetworkBrowser BrowseAllInterfaces 1i

###############################################################################
# Dock, Dashboard, and hot corners                                            #
###############################################################################

# Set the icon size of Dock items to 54 pixels
defaults write com.apple.dock tilesize -int 54

# Minimize windows into their application’s icon
defaults write com.apple.dock minimize-to-application -bool true

# Speed up Mission Control animations
defaults write com.apple.dock expose-animation-duration -float 0.2

# Make Dock icons of hidden applications translucent
defaults write com.apple.dock showhidden -bool true

# Dock magnification
defaults write com.apple.dock magnification -bool true
defaults write com.apple.dock largesize -int 100


# Dock orientation: 'left', 'bottom', 'right'
defaults write com.apple.dock 'orientation' -string 'bottom'

# Double-click a window's title bar to:
# None
# Mimimize
# Maximize (zoom)
defaults write NSGlobalDomain AppleActionOnDoubleClick -string "Maximize"

# Show indicator lights for open applications
defaults write com.apple.dock show-process-indicators -bool true

###############################################################################
# Photos                                                                      #
###############################################################################

# Prevent Photos from opening automatically when devices are plugged in
defaults -currentHost write com.apple.ImageCapture disableHotPlug -bool true

###############################################################################
# Siri
###############################################################################

# Enable Siri
defaults write com.apple.assistant.support "Assistant Enabled" -bool true

# Language
defaults write com.apple.assistant.backedup "Session Language" -string "he-IL"

###############################################################################
# App Store
###############################################################################

# Download newly available updates in the background
sudo defaults write /Library/Preferences/com.apple.SoftwareUpdate AutomaticDownload -bool true

# Install app updates
sudo defaults write /Library/Preferences/com.apple.commerce AutoUpdate -bool true
