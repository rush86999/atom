---
name: shopify-content
description: Create Shopify product listings and blog articles/posts automatically via the shopify_* tools
version: 1.0.0
author: Atom Team
tags: [shopify, ecommerce, product, listing, blog, article, content]
maturity_level: SUPERVISED
governance:
  maturity_requirement: SUPERVISED
  reason: "Publishing product listings and blog posts changes the storefront; requires supervision by default"
---

# Shopify Content Automation

Publish product listings and blog posts to the connected Shopify store using the
`shopify_*` MCP tools. The store must be connected first (Settings → Shopify).

## Prerequisite

Verify a store is connected before doing anything else:

1. Call `shopify_get_products` (limit 1). If it returns "No Shopify store
   connected to this workspace.", tell the user to connect a store first and stop.

## Create a product listing

1. Call `shopify_create_product` with:
   - `title` (required) — clear, searchable product name.
   - `body_html` — description as HTML (bullet points convert well: `<ul><li>...`).
   - `vendor`, `product_type`, `tags` (comma separated).
   - `variants` — array of `{title, price, sku, inventory_quantity}`; set a
     real `price` and `sku` when you have them.
   - `images` — array of `{src: "https://..."}` public image URLs, or plain URL
     strings. Skip if you have no images rather than inventing URLs.
2. Report the created product id and handle back to the user.

## Create a blog post

1. Call `shopify_list_blogs`. Pick the target blog by `id`.
   - If no blogs exist, call `shopify_create_blog` first
     (`title`, optional `handle`) and use the returned `id`.
2. Call `shopify_create_article` with:
   - `blog_id` (required) — the blog id from step 1.
   - `title` (required)
   - `body_html` (required) — the post body as HTML (headings `<h2>`, paragraphs
     `<p>`, lists `<ul>`). Never pass plain markdown as if it were HTML.
   - `author` (optional), `tags` (optional, comma separated), `published`
     (default true).
3. Report the article id and public `url` back to the user.

## Rules

- Never fabricate prices, SKUs, image URLs, or product data — ask the user or
  use data you actually have.
- Prefer `draft` status (`status: "draft"`) for listings that need a human
  review before going live.
- If a call fails with a Shopify API error, surface the store's error message
  verbatim so the user can fix permissions/scopes, then stop.
