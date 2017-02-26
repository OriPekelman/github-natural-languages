# Analyse natural language READMEs on Github

What this project intends to do is to detect the main language on each and every Github repository. There are clearly
linguistic islands in Open Source and this is a first attempt at mapping those.

This will not go very far with the Github rate limits (not fully implemented anyway).. so for the moment this is
an unfinished toy.

For the moment all this does is cycle through the repos on github, detect the languages and put everything in Elastic Search

# Setup

export the environment or create a .env file with something in the lines of:
```
GITHUB_TOKEN="6df7....2d12af12b82f00"
REDIS_URL="redis://localhost"
ELASTICSEARCH_URL="http://localhost:9200"
```

# Running

celery -A run worker --loglevel=info

# Rate limiting

Not yet implemented
