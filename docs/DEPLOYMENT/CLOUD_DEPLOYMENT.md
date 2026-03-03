# CLOUD DEPLOYMENT

> **Status**: Template - Content needed
> **Last Updated**: 2025-11-10

## Overview

This documentation is currently being organized. Content will be added soon.

## TODO

- [ ] Add comprehensive content
- [ ] Include examples and use cases
- [ ] Add troubleshooting information
- [ ] Include best practices

## DigitalOcean App Platform (1-Click Deploy)

Atom is optimized for DigitalOcean App Platform, providing a seamless scaling path from prototype to production.

### Quick Start: 1-Click Deploy

Click the button below to launch Atom on DigitalOcean:

[![Deploy to DO](https://www.deploytodo.com/do-btn-blue.svg)](https://cloud.digitalocean.com/apps/new?repo=https://github.com/rush86999/atom/tree/main&config=deploy/digitalocean/app.yaml)

### Manual Setup

1. **Prerequisites**: A DigitalOcean account and the `doctl` CLI (optional).
2. **Create New App**: Go to the Apps dashboard and select "New App".
3. **Connect GitHub**: Choose the `rush86999/atom` repository.
4. **Configuration**: The App Platform will automatically detect the components using the `deploy/digitalocean/app.yaml` file.
5. **Set Secrets**: Ensure you provide values for `SECRET_KEY`, `JWT_SECRET_KEY`, and `BYOK_ENCRYPTION_KEY` in the App settings.
6. **Deploy**: Click "Create Resources" to start the deployment.

### Features
- **Managed Database**: Real-time PostgreSQL scaling.
- **Zero-Downtime**: Automatic rolling updates on every push to `main`.
- **Integrated Monitoring**: Built-in logs and metrics.

## Troubleshooting

Content coming soon...

---

**Need Help?** Check the main [documentation index](../README.md) for more resources.

**Found an Issue?** Help us improve by contributing to the documentation.
