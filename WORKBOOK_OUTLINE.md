# RESITING Project Workbook Outline

> **Note:** This document provides a quick reference to the project files and datasets.

This workbook contains geospatial data layers, project metadata, and environment configuration scripts.

## 1. Global Geospatial Datasets (Natural Earth)
- **Admin 0 - Countries** (`ne_110m_admin_0_countries`)
  - **Scale:** 1:110m
  - **Description:** De facto boundary polygons for 258 countries worldwide.
- **Admin 1 - States, Provinces** (`ne_110m_admin_1_states_provinces`)
  - **Scale:** 1:110m
  - **Description:** Internal, first-order administrative boundary polygons (e.g., states and provinces).

## 2. Regional Geospatial Datasets (Thailand)
- **Admin Level 1 Boundaries** (`tha_admbnda_adm1_rtsd_20220121`)
  - **Source:** Royal Thai Survey Department (RTSD) / UNOCHA
  - **Description:** 77 administrative boundary polygons representing the provinces of Thailand.
  - **CRS:** WGS 1984 (EPSG:4326)
- **Transportation Network** (`Trans`)
  - **Source:** GISTDA
  - **Description:** Road and transportation polyline data containing 88,124 segment features in Thailand.
  - **CRS:** WGS 1984 (EPSG:4326)

## 3. Scripts & Configurations
- **CDS API Configuration Script** (`modify_cdsapi.txt`)
  - **Language:** Python
  - **Description:** Contains the `get_url_key_verify` utility function to parse and resolve authentication keys from `~/.cdsapirc` or environment variables, used for accessing the Copernicus Climate Data Store API.