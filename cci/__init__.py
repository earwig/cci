from pywikiapi import wikipedia

site = wikipedia('en', headers={
    'User-Agent': 'Mozilla/5.0 (compatible; EarwigBotCCI/0.1; +wikipedia.earwig@gmail.com)'
})
