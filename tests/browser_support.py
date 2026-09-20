"""Choose local Chrome or CI's bundled Chromium. Author: donglixiao."""
import os


def launch_browser(playwright):
    channel = os.environ.get('MEMOIR_BROWSER_CHANNEL', 'chrome')
    return playwright.chromium.launch(channel=None if channel == 'bundled' else channel, headless=True)
