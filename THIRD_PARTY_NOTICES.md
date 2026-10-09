# Third-Party Notices

## Bootstrap and Bootswatch Flatly

The Dash UI uses [bootstrap.min.css](streamlit/workspaces/assets/bootstrap.min.css), a Bootstrap 5.3.8 distribution styled with the Bootswatch Flatly theme. The file header identifies Bootswatch copyright 2012-2025 Thomas Park and Bootstrap copyright 2011-2025 The Bootstrap Authors. Both are distributed under the MIT License. Upstream sources and license terms are available from [Bootswatch](https://github.com/thomaspark/bootswatch/tree/v5.3.8) and [Bootstrap](https://github.com/twbs/bootstrap/blob/v5.3.8/LICENSE).

The MIT License permits use, modification, distribution, sublicensing, and sale provided the copyright and permission notice are included with copies or substantial portions of the software. The software is provided "as is", without warranty or liability.

Only the minified Flatly stylesheet used by `dash_app.py` is retained; other Bootstrap build variants and source maps are not loaded by either app.

## Bundled OpenAgri Media and Data

The repository contains OpenAgri-branded logo files and drone imagery under `streamlit/workspaces/icons/`, `streamlit/workspaces/assets/`, and `streamlit/workspaces/static/`. The root project notice describes the OpenAgri work and funding but does not identify the creator, source, or separate license for each media file. Do not assume the root Apache-2.0 license establishes rights to third-party media; maintainers should record the source and license or obtain confirmation before redistributing externally sourced files.

Airport shapefile components were previously present under `streamlit/workspaces/`, but their source and license are not documented here. Record source and license terms before restoring or redistributing that data.