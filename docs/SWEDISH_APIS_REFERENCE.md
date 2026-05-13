> **Migrated 2026-04-21 from legacy edvin-solar-master.** Original catalog of Swedish property/geospatial APIs (Lantmäteriet, Metria, SMHI, Copernicus, etc.). Kept for reference when planning enrichment sources.

# APIs, Data Sources & Services for Solar Panel Prospecting in Sweden

## 1. SWEDISH PROPERTY / FASTIGHET REGISTRIES

### 1.1 Lantmateriet - Fastighetsregistret (Direct Access)
- **What it provides:** Property boundaries, property IDs (fastighetsbeteckning), owners, purchase price, assessed values (taxeringsvarde), mortgages, easements, building data for all ~3.4 million Swedish properties
- **URL:** https://www.lantmateriet.se/sv/geodata/vara-produkter/produktsupport/api-portalen/
- **Open Data Portal:** https://opendata.lantmateriet.se/
- **Pricing:** Many datasets became fee-free from February 1, 2025 under law (2022:818). Some property register data still requires license agreements. Non-commercial use = 0.1x license fee. Fees documented at: https://www.lantmateriet.se/globalassets/geodata/geodataprodukter/avgifter_och_leveransinformation_for_geodata.pdf
- **Access:** Requires application and API key via their API Portal (production + verification environments)
- **Relevance:** CRITICAL - Core data source for property identification, owner lookup, and building data

### 1.2 TIC (The Intelligence Company) - Property API
- **What it provides:** Complete property reports with owner info, purchase price, assessed values, area, mortgages, easements, buildings, orthophotos, maps, and residents registered at the property. All sourced from Lantmateriet. Millisecond response times.
- **URL:** https://tic.io/en/developers/property-information
- **Pricing:** Not publicly listed - contact for quote. Likely per-query pricing.
- **Access:** REST API with auto-generated client classes
- **Relevance:** HIGH - Convenient commercial wrapper around Lantmateriet data with additional enrichment (residents at property). Easier integration than direct Lantmateriet access.

### 1.3 Metria - Fastighetsdata
- **What it provides:** Real estate information for all Swedish properties, sourced from Lantmateriet
- **URL:** https://metria.se/en/knowledge/how-to-access-real-estate-information-about-all-of-swedens-properties
- **Pricing:** Commercial - contact for quote
- **Relevance:** HIGH - Alternative commercial reseller of Lantmateriet property data

### 1.4 Bolagsverket API (Company Registry)
- **What it provides:** Company information for Swedish businesses (useful if targeting commercial buildings)
- **URL:** https://bolagsverket.se/apierochoppnadata.2531.html
- **Pricing:** Some data is open/free, other requires fees
- **Relevance:** MEDIUM - Relevant for commercial property owners

---

## 2. AERIAL / SATELLITE IMAGERY SOURCES

### 2.1 Lantmateriet - Ortofoto (Orthophoto)
- **What it provides:** Geometrically accurate aerial images covering all of Sweden. ~30% of Sweden re-photographed annually. Southern Sweden every 2 years, northern every 2-4 years. Available via STAC API. Historical orthophotos from 1949-2005 also available.
- **URL:** https://www.lantmateriet.se/en/geodata/our-products/product-list/orthophoto/
- **Pricing:** Now available as open data (CC0 license) since Feb 2025 for many products
- **Access:** STAC API, WMS server, bulk download
- **Relevance:** CRITICAL - Free high-quality aerial imagery of all Swedish rooftops for ML-based solar panel detection

### 2.2 Google Maps / Google Earth Imagery
- **What it provides:** Satellite and aerial imagery globally, including Sweden
- **URL:** https://developers.google.com/maps/documentation/maps-static/overview
- **Pricing:** Pay-as-you-go via Google Maps Platform. $200/month free usage threshold ended Feb 2025, replaced with free usage tiers.
- **Relevance:** HIGH - Good supplementary imagery source with frequent updates in urban areas

### 2.3 Maxar (formerly DigitalGlobe)
- **What it provides:** Highest commercial resolution (30 cm native, 15 cm HD). Archive + fresh tasking. Up to 15 revisits/day. European distribution via European Space Imaging.
- **URL:** https://www.maxar.com/maxar-intelligence/products/satellite-imagery
- **Pricing:** Expensive. Archive imagery ~$14-24/sq km depending on age/resolution. New tasking significantly more. Subscription plans (MGP Pro) available.
- **Relevance:** MEDIUM - Overkill for most use cases since Lantmateriet ortofoto is free, but useful for very recent imagery needs

### 2.4 Airbus OneAtlas
- **What it provides:** 30 cm very high-resolution optical imagery via Pleiades Neo constellation. Global coverage including Sweden.
- **URL:** https://space-solutions.airbus.com/imagery/how-to-order-imagery-and-data/
- **Pricing:** Commercial - subscription and per-image pricing available
- **Relevance:** MEDIUM - Same reasoning as Maxar

### 2.5 Nearmap
- **What it provides:** Ultra-high resolution aerial imagery with AI-powered solar panel detection built in. Includes Solar Panel AI pack that distinguishes PV panels from solar hot water panels.
- **URL:** https://www.nearmap.com/au/solutions/solar
- **API docs:** https://www.nearmap.com/products/integrations-apis
- **Pricing:** Subscription-based - contact for quote. Coverage primarily US/AU/NZ/Canada. Limited European coverage.
- **Relevance:** LOW for Sweden - Coverage may not include Sweden. Worth checking current European expansion.

### 2.6 Vexcel Data Program
- **What it provides:** Aerial imagery and elevation data of Sweden
- **URL:** https://vexceldata.com/countries/sweden/
- **Pricing:** Commercial subscription
- **Relevance:** MEDIUM - Alternative commercial aerial imagery provider with Swedish coverage

---

## 3. SOLAR POTENTIAL ASSESSMENT TOOLS

### 3.1 Google Solar API
- **What it provides:** Building-level solar potential analysis including: roof segment geometry, annual sunshine hours, solar panel layout optimization, energy production estimates. Sweden has medium-quality coverage with 472+ million buildings analyzed globally.
- **URL:** https://developers.google.com/maps/documentation/solar/overview
- **Coverage:** https://developers.google.com/maps/documentation/solar/coverage
- **Pricing:** Pay-as-you-go. BuildingInsights: free up to 10,000 requests/month, then usage-based. DataLayers: free up to 1,000 requests/month, then significantly higher cost. Max 600 queries/minute.
- **Access:** REST API via Google Cloud Platform
- **Relevance:** CRITICAL - Best single API for solar potential assessment. Provides roof geometry, optimal panel placement, and energy estimates. Swedish coverage confirmed.

### 3.2 PVGIS (Photovoltaic Geographical Information System)
- **What it provides:** Solar radiation data, PV system performance estimates for any location worldwide. Accounts for panel type (crystalline silicon default), mounting type, inclination, orientation, temperature, and wind. Uses PVGIS-SARAH2 dataset for Europe (0.05 x 0.05 degree resolution). 7.4+ million users.
- **URL:** https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis_en
- **API docs:** https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/getting-started-pvgis/api-non-interactive-service_en
- **Pricing:** FREE - Developed by EU Joint Research Centre
- **Access:** REST API (PVGIS 5.3 current), callable from Python, NodeJS, Java, etc.
- **Relevance:** CRITICAL - Free, accurate solar radiation and PV yield estimates. Essential for calculating ROI for prospective customers.

### 3.3 SMHI STRANG API (Solar Radiation Data)
- **What it provides:** Hourly and daily solar radiation data for the Nordic countries. Global radiation, direct radiation, UV radiation, photosynthetically active radiation. 2.5 x 2.5 km grid resolution, 630 x 779 grid size. Data from 1999 onward.
- **URL:** https://opendata.smhi.se/apidocs/strang/
- **Data extraction:** https://strang.smhi.se/extraction/index.php
- **Pricing:** FREE - Open data from Swedish government
- **Access:** REST API
- **Relevance:** HIGH - Sweden-specific solar radiation data. More localized than PVGIS for Swedish conditions. Excellent for validating solar potential estimates.

### 3.4 SMHI Open Data - Meteorological Observations
- **What it provides:** Temperature, precipitation, wind, air pressure, cloud cover from Swedish observation stations. Useful for estimating real-world panel efficiency (temperature coefficient, snow cover, etc.)
- **URL:** https://opendata.smhi.se/
- **Pricing:** FREE
- **Relevance:** MEDIUM - Supplementary weather data for accurate yield modeling

### 3.5 Lantmateriet - Elevation Model (Hojdmodell)
- **What it provides:** LiDAR-based terrain model at 1-meter grid resolution. Critical for calculating roof slope, aspect, and shading analysis. Based on national LiDAR scanning (Ny Nationell Hojdmodell). Includes slope visualization and hillshade.
- **URL:** https://www.lantmateriet.se/en/geodata/our-products/product-list/elevation-model-download/
- **Pricing:** Free since Feb 2025 (open data)
- **Access:** Download + view service (WMS)
- **Relevance:** HIGH - Essential for roof slope/aspect calculations and shadow analysis when Google Solar API data is insufficient

### 3.6 Swedish Municipal Solkartor (Solar Maps)
- **What it provides:** Pre-calculated solar potential for rooftops in 31+ Swedish municipalities (all 26 Stockholm County municipalities + others). Built on SEES GIS tool developed by WSP and Gothenburg University. Shows actual roof area and total solar radiation per roof.
- **URL:** https://svensksolenergi.se/att-installera-solenergi/solkartor/
- **Example:** https://www.storsthlm.se/samverkansomraden/infrastruktur/energi-och-klimatradgivningen/solkarta/
- **Pricing:** Free for end users on municipal websites. Underlying SEES platform developed by WSP.
- **Relevance:** MEDIUM - Pre-calculated data for major municipalities. Not API-accessible but could be scraped or licensed. Contact WSP for platform access.

### 3.7 Aurora Solar API
- **What it provides:** Full solar design platform with API. Automated project creation from lead forms, system design based on satellite imagery and insolation data, shade analysis, energy production modeling, financial analysis.
- **URL:** https://docs.aurorasolar.com/
- **API reference:** https://docs.aurorasolar.com/reference/aurora-solar-api
- **Pricing:** Subscription-based platform. API access included with Aurora Solar subscription. Contact for pricing.
- **Relevance:** HIGH - Industry-leading solar design tool. Could serve as the calculation engine for your prospecting tool if budget allows.

---

## 4. PERSON / ADDRESS LOOKUP (POPULATION REGISTRY)

### 4.1 SPAR (Statens Personadressregister)
- **What it provides:** Name, address (structured with kommun/region), personal ID number for all persons registered as resident in Sweden. Updated daily from Swedish Population Register. SOAP API.
- **URL:** https://www.statenspersonadressregister.se/
- **Pricing:** Requires application and agreement. Fees apply per transaction. Organizations must demonstrate legitimate purpose (e.g., direct marketing requires opt-out compliance).
- **Access:** SOAP API. Application process through Skatteverket.
- **GDPR note:** Strict rules on usage. Direct marketing use requires specific legal basis.
- **Relevance:** CRITICAL - Official source for property owner contact information. Required for any outreach campaign.

### 4.2 Skatteverket Navet (Folkbokforing API)
- **What it provides:** Personal numbers, names, addresses, registration properties, apartment numbers, districts. Search by personnummer or by name+address combination.
- **URL:** https://www7.skatteverket.se/portal/apier-och-oppna-data/utvecklarportalen/api/folkbokforingsuppgifter-for-offentliga-aktorer/2.0.0
- **Pricing:** 0.02 SEK per person record lookup, 0.50 SEK per name search
- **Access:** Restricted to public actors (myndigheter, kommuner, regioner). Private companies should use SPAR instead.
- **Relevance:** LOW for commercial use - Only available to public sector organizations

### 4.3 Marknadsinformation.se - SPAR Address API
- **What it provides:** Commercial SPAR data reseller. JSON API for address lookup by phone number, personnummer, or org.number. Regularly updated against SPAR. Target group selection for marketing.
- **URL:** https://www.marknadsinformation.se/api-adressuppgifter
- **Pricing:** Standard API lookups described as free for basic queries. Volume pricing on request.
- **Relevance:** HIGH - Easier commercial access to SPAR data than applying directly. Good for enriching property owner data with contact details.

### 4.4 Hitta.se API
- **What it provides:** Person search (name, address, phone number), company search, map/driving directions. Annual reports for 400,000+ companies. Coverage limited to Sweden.
- **URL:** https://www.hitta.se/ (API docs at https://www.hitta.se/api)
- **GitHub PHP wrapper:** https://github.com/argia-andreas/hitta.se-php-api
- **Pricing:** API usage incurs fees. Basic web access is free. Rate limits apply.
- **Relevance:** HIGH - Quick lookups for phone numbers and addresses. Useful for enriching prospect data.

### 4.5 Ratsit
- **What it provides:** Person search, address lookup, phone numbers, income data, tax records, credit information for individuals across Sweden
- **URL:** https://www.ratsit.se/
- **Pricing:** Free basic lookups on web. Premium/API access requires subscription.
- **Relevance:** MEDIUM - Useful for enrichment but primarily web-based. Less suitable for bulk API integration.

### 4.6 Eniro.se
- **What it provides:** Person and business directory. Phone numbers, addresses, company information. Operates across Nordics (Sweden, Norway, Denmark, Finland).
- **URL:** https://www.eniro.se/
- **Pricing:** Free basic lookups. API/commercial use requires agreement.
- **Relevance:** MEDIUM - Alternative to Hitta.se for contact enrichment

### 4.7 Dun & Bradstreet (formerly Bisnode) - Nordic APIs
- **What it provides:** Credit information for persons (Sweden, Norway, Finland, Denmark), company data, vehicle data. OAuth2 authentication.
- **URL:** https://www.dnb.com/developers-nordics/
- **Pricing:** Commercial - per-query pricing
- **Relevance:** LOW-MEDIUM - More relevant for B2B credit checks than residential solar prospecting

---

## 5. BUILDING FOOTPRINT & 3D DATA

### 5.1 Lantmateriet - Byggnad Nedladdning (Building Download)
- **What it provides:** 9.3 million building footprints across Sweden with building type/purpose and name. High-quality 2D polygons. Released as open data February 2025.
- **URL:** https://www.lantmateriet.se/en/geodata/our-products/product-list/building-download-vector/
- **INSPIRE version:** https://www.lantmateriet.se/en/geodata/geodata-products/product-list/buildning-download-inspire/
- **Pricing:** FREE (CC0 license since Feb 2025)
- **Access:** Atom feed download, by municipality
- **Relevance:** CRITICAL - Free building footprints for all of Sweden. Essential for identifying residential rooftops and filtering by building type.

### 5.2 OpenStreetMap - Overpass API
- **What it provides:** Building footprints, some tagged solar installations (generator:source=solar), building types. Query by bounding box or area.
- **URL:** https://wiki.openstreetmap.org/wiki/Overpass_API
- **Interactive tool:** https://overpass-turbo.eu/
- **Pricing:** FREE (open data, ODbL license)
- **Relevance:** MEDIUM - Good supplementary source. Solar panel tags exist but coverage is very incomplete. Building footprints less complete than Lantmateriet.

### 5.3 OSM Buildings
- **What it provides:** 3D building data derived from OpenStreetMap, including building heights
- **URL:** https://osmbuildings.org/data/
- **Pricing:** Free for non-commercial use
- **Relevance:** LOW - Less complete than Lantmateriet for Sweden

---

## 6. COMPUTER VISION / ML FOR SOLAR PANEL DETECTION

### 6.1 Custom YOLO / Deep Learning Models
- **What it provides:** Train your own solar panel detection model using YOLO (v5/v8/v11) on satellite/aerial imagery. 93%+ classification accuracy achievable. Can be formulated as classification, object detection, or semantic segmentation.
- **Training data:** Use Lantmateriet ortofoto + manually labeled examples
- **Frameworks:** Ultralytics YOLO, Detectron2, MMDetection
- **Key resource:** https://www.satellite-image-deep-learning.com/p/solar-panel-detection-with-satellite
- **Pricing:** Compute costs only (GPU training/inference)
- **Relevance:** CRITICAL - Most cost-effective approach for large-scale scanning. Train on Swedish imagery for best results.

### 6.2 Roboflow
- **What it provides:** End-to-end computer vision platform. Pre-trained solar panel detection models available. Dataset hosting, labeling, training, and deployment. REST API for inference.
- **URL:** https://blog.roboflow.com/identify-solar-panels-in-aerial-imagery/
- **Pre-trained model:** https://universe.roboflow.com/brad-dwyer/aerial-solar-panels
- **Pricing:** Free tier (1,000 inferences/month), then from $249/month for Pro
- **Relevance:** HIGH - Fastest path to a working solar panel detector. Pre-trained models available.

### 6.3 Amazon Rekognition Custom Labels
- **What it provides:** AWS service for training custom image classifiers. Amazon published a specific tutorial for solar panel detection from aerial imagery. Uses SageMaker Ground Truth for labeling.
- **URL:** https://aws.amazon.com/blogs/machine-learning/identify-rooftop-solar-panels-from-satellite-imagery-using-amazon-rekognition-custom-labels/
- **Pricing:** $1/hour for training, $4/hour per inference unit
- **Note:** Amazon Rekognition Custom Labels was deprecated. Use Amazon Bedrock or SageMaker instead.
- **Relevance:** MEDIUM - AWS ecosystem approach. Consider Amazon SageMaker for current implementation.

### 6.4 Google Cloud Vision API / Vertex AI
- **What it provides:** Custom model training for image classification and object detection. AutoML Vision for low-code training. Can be trained on solar panel imagery.
- **URL:** https://cloud.google.com/vertex-ai
- **Pricing:** Pay-per-use. AutoML training ~$3.15/node hour. Prediction ~$0.06/node hour.
- **Relevance:** MEDIUM - Good if already in Google Cloud ecosystem (pairs well with Google Solar API)

### 6.5 Open Source Datasets & Models
- **What it provides:** Pre-existing labeled datasets for solar panel detection
- **Key repositories:**
  - https://github.com/saizk/Deep-Learning-for-Solar-Panel-Recognition
  - https://github.com/riccardocadei/photovoltaic-detection (EPFL)
  - https://github.com/A-Stangeland/SolarDetection
  - HyperionSolarNet: https://arxiv.org/pdf/2201.02107
- **Pricing:** FREE (open source)
- **Relevance:** HIGH - Starting point for training data and model architectures. May need fine-tuning on Swedish imagery.

---

## 7. SWEDISH ENERGY DATA

### 7.1 Energimyndigheten (Swedish Energy Agency)
- **What it provides:** Statistics on solar PV installations (number and capacity) by size and municipality. Energy balance data. Fuel prices. Official energy statistics authority.
- **URL:** https://www.energimyndigheten.se/en/facts-and-figures/statistics/
- **Pricing:** Free (public statistics)
- **Access:** Via website and through Apiverket
- **Relevance:** HIGH - Municipal-level solar installation statistics. Useful for identifying under-penetrated areas for prospecting.

### 7.2 Energimarknadsinspektionen (Ei) - Open Data
- **What it provides:** Open data on the Swedish energy market. Grid operator information, electricity pricing data.
- **URL:** https://ei.se/om-oss/statistik-och-oppna-data/oppna-data
- **Pricing:** FREE
- **Relevance:** MEDIUM - Useful for understanding grid pricing and identifying areas where solar ROI is highest

### 7.3 Svenska Kraftnat (SVK) - Control Room Data
- **What it provides:** National electricity production data including solar power production by price area. Hourly data from balance responsible parties.
- **URL:** https://www.svk.se/en/national-grid/the-control-room/
- **Pricing:** FREE
- **Relevance:** LOW - Macro-level production data, less relevant for individual property prospecting

### 7.4 Grid Operator (Natagar) APIs
- **What it provides:** Individual energy consumption and production data for customers
- **Examples:**
  - Oresundskraft: https://www.oresundskraft.se/foretag/energitjanster/energidata-genom-api/
  - E.ON Energidata API: https://www.eon.se/foeretag/integrerade-energiloesningar/fa-koll-pa-er-forbrukning/energidata-api
  - Goteborg Energi + Tekniska verken (open API with RISE)
- **Pricing:** Varies by operator. Some free for customers.
- **Relevance:** MEDIUM - Useful if you can access consumption data to calculate savings potential for specific properties

### 7.5 Open Power System Data
- **What it provides:** European power system data including installed capacity by country/technology, individual power plant locations, time series for consumption and renewable generation
- **URL:** https://open-power-system-data.org/
- **Data:** https://data.open-power-system-data.org/renewable_power_plants/
- **Pricing:** FREE
- **Relevance:** MEDIUM - Contains locations of existing solar installations in Sweden

---

## 8. AGGREGATOR / META APIs

### 8.1 Apiverket - Sweden's Public Data API
- **What it provides:** Single REST API for 280+ endpoints from 45+ Swedish government sources including SCB statistics, Energimyndigheten, weather data, transport, company data
- **URL:** https://apiverket.se
- **Pricing:** Free tier: 200 requests/day. Paid plans for higher volume.
- **Relevance:** MEDIUM - Convenient single-key access to multiple Swedish data sources

### 8.2 Signicat - Data Verification (SPAR Integration)
- **What it provides:** SPAR data verification through Signicat's platform. Identity verification and address lookup.
- **URL:** https://developer.signicat.com/docs/data-verification/data-sources/persons/spar-statens-personadressregister/
- **Pricing:** Commercial - per-verification pricing
- **Relevance:** MEDIUM - Alternative SPAR access path through identity verification provider

---

## 9. RECOMMENDED ARCHITECTURE STACK

For a commercial solar panel prospecting tool in Sweden, here is the recommended priority order:

### Phase 1: Detect Existing Solar Panels
1. **Lantmateriet Ortofoto** (free) - Aerial imagery of all Sweden
2. **Lantmateriet Byggnad** (free) - 9.3M building footprints to identify rooftops
3. **Custom YOLO model** or **Roboflow** - Detect solar panels on rooftops from imagery
4. **Google Solar API** (Expanded Coverage) - Cross-reference with detected arrays feature

### Phase 2: Get Property & Owner Data
5. **Lantmateriet Fastighetsregistret** or **TIC API** - Property owner, assessed value, building details
6. **SPAR** or **Marknadsinformation.se** - Owner name and contact address
7. **Hitta.se API** - Phone numbers for outreach

### Phase 3: Assess Solar Potential
8. **Google Solar API** - Roof geometry, optimal panel layout, energy estimates
9. **PVGIS** (free) - Solar radiation and PV yield calculations
10. **SMHI STRANG** (free) - Sweden-specific solar radiation validation
11. **Lantmateriet Hojdmodell** (free) - Roof slope/aspect from LiDAR

### Phase 4: Prioritize Prospects
12. **Energimyndigheten** statistics - Municipal penetration rates
13. **Ei open data** - Grid pricing to calculate ROI by area
14. **Energidata APIs** (E.ON, etc.) - Consumption data where available

---

## 10. KEY LEGAL CONSIDERATIONS

- **GDPR:** Any use of personal data (names, addresses, phone numbers) from SPAR/Hitta/Ratsit requires a legal basis. Direct marketing typically requires legitimate interest assessment and opt-out mechanisms.
- **SPAR access:** Requires formal application and demonstrated legitimate purpose
- **Lantmateriet data reuse:** Open data products are CC0. Property register data may have specific license terms.
- **Google Solar API EEA terms:** Special terms apply from July 8, 2025 for EEA billing addresses
- **Telemarketing:** Swedish law (marknadsforingslagen) regulates unsolicited contact. NIX-Telefon opt-out register must be checked before cold calling.
