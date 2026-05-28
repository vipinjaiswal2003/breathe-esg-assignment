"""
Management command to seed the database with sample data:
- A tenant (Acme Manufacturing)
- Two users (admin + analyst)
- Three data sources (SAP, Utility, Travel)
- Emission factors (global defaults)
- Sample ingestion batches with raw and normalized records
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from datetime import date, datetime
import json

from tenants.models import Tenant, TenantMembership
from ingestion.models import (
    DataSource, IngestionBatch,
    RawSAPRecord, RawUtilityRecord, RawTravelRecord,
    EmissionFactor, NormalizedEmission,
)


class Command(BaseCommand):
    help = 'Seed the database with sample data for development'

    def handle(self, *args, **options):
        self.stdout.write('Seeding database...\n')

        # Create tenant
        tenant, _ = Tenant.objects.get_or_create(
            slug='acme-manufacturing',
            defaults={
                'name': 'Acme Manufacturing Pvt. Ltd.',
                'industry': 'Manufacturing',
                'reporting_year_start': date(2024, 4, 1),
            }
        )
        self.stdout.write(f'  Tenant: {tenant.name}')

        # Create users
        admin_user, _ = User.objects.get_or_create(
            username='admin',
            defaults={
                'is_superuser': True,
                'is_staff': True,
                'email': 'admin@acme.com',
                'first_name': 'Admin',
                'last_name': 'User',
            }
        )
        admin_user.set_password('admin123')
        admin_user.save()

        analyst_user, _ = User.objects.get_or_create(
            username='analyst',
            defaults={
                'is_staff': True,
                'email': 'analyst@breatheesg.com',
                'first_name': 'Priya',
                'last_name': 'Sharma',
            }
        )
        analyst_user.set_password('analyst123')
        analyst_user.save()

        # Create memberships
        TenantMembership.objects.get_or_create(
            user=admin_user, tenant=tenant,
            defaults={'role': 'admin'},
        )
        TenantMembership.objects.get_or_create(
            user=analyst_user, tenant=tenant,
            defaults={'role': 'analyst'},
        )
        self.stdout.write(f'  Users: admin/admin123, analyst/analyst123')

        # Create data sources
        sap_source, _ = DataSource.objects.get_or_create(
            tenant=tenant, name='SAP S/4HANA — India Operations',
            defaults={
                'source_type': 'sap',
                'ingestion_mechanism': 'file_upload',
                'config': {
                    'plant_code_mapping': {
                        '1000': 'Mumbai Plant',
                        '2000': 'Delhi Plant',
                        '3000': 'Bangalore Plant',
                    },
                    'date_format': 'DD.MM.YYYY',
                },
            }
        )

        utility_source, _ = DataSource.objects.get_or_create(
            tenant=tenant, name='Utility Portal — Tata Power',
            defaults={
                'source_type': 'utility',
                'ingestion_mechanism': 'file_upload',
                'config': {
                    'timezone': 'Asia/Kolkata',
                    'default_multiplier': 1.0,
                },
            }
        )

        travel_source, _ = DataSource.objects.get_or_create(
            tenant=tenant, name='SAP Concur — Corporate Travel',
            defaults={
                'source_type': 'travel',
                'ingestion_mechanism': 'file_upload',
                'config': {
                    'platform': 'concur',
                    'api_version': 'v4',
                },
            }
        )
        self.stdout.write('  Data sources: SAP, Utility, Travel')

        # Create emission factors
        self._create_emission_factors()
        self.stdout.write('  Emission factors: created')

        # Create sample data
        self._create_sap_sample(tenant, sap_source, admin_user)
        self._create_utility_sample(tenant, utility_source, admin_user)
        self._create_travel_sample(tenant, travel_source, admin_user)

        self.stdout.write(self.style.SUCCESS('\nSeeding complete!'))

    def _create_emission_factors(self):
        """Create global emission factors."""
        factors = [
            # Scope 1 - Stationary Combustion
            {'scope': 'scope1', 'category': 'stationary_combustion',
             'activity_name': 'Diesel — stationary combustion',
             'fuel_or_activity_type': 'diesel', 'co2e_factor': 2.676,
             'unit': 'liter', 'source': 'DEFRA 2024', 'year': 2024},
            {'scope': 'scope1', 'category': 'stationary_combustion',
             'activity_name': 'Natural Gas — stationary combustion',
             'fuel_or_activity_type': 'natural_gas', 'co2e_factor': 2.021,
             'unit': 'kg', 'source': 'DEFRA 2024', 'year': 2024},
            {'scope': 'scope1', 'category': 'mobile_combustion',
             'activity_name': 'Diesel — mobile combustion (vehicles)',
             'fuel_or_activity_type': 'diesel_mobile', 'co2e_factor': 2.702,
             'unit': 'liter', 'source': 'DEFRA 2024', 'year': 2024},
            {'scope': 'scope1', 'category': 'stationary_combustion',
             'activity_name': 'Gasoline — stationary combustion',
             'fuel_or_activity_type': 'gasoline', 'co2e_factor': 2.196,
             'unit': 'liter', 'source': 'DEFRA 2024', 'year': 2024},
            {'scope': 'scope1', 'category': 'stationary_combustion',
             'activity_name': 'LPG — stationary combustion',
             'fuel_or_activity_type': 'lpg', 'co2e_factor': 1.549,
             'unit': 'liter', 'source': 'DEFRA 2024', 'year': 2024},
            # Scope 2 - Purchased Electricity
            {'scope': 'scope2', 'category': 'purchased_electricity_location',
             'activity_name': 'India Grid — 2023 (CEA)',
             'fuel_or_activity_type': 'grid_india', 'co2e_factor': 726.0,
             'unit': 'MWh', 'source': 'India CEA 2023', 'year': 2023},
            {'scope': 'scope2', 'category': 'purchased_electricity_location',
             'activity_name': 'US Grid Average — eGRID 2022',
             'fuel_or_activity_type': 'grid_us', 'co2e_factor': 387.0,
             'unit': 'MWh', 'source': 'EPA eGRID 2022', 'year': 2022},
            # Scope 3 - Business Travel
            {'scope': 'scope3', 'category': 'business_travel_air',
             'activity_name': 'Flight — Economy, short-haul',
             'fuel_or_activity_type': 'flight_economy_shorthaul', 'co2e_factor': 0.15659,
             'unit': 'passenger-km', 'source': 'DEFRA 2024', 'year': 2024},
            {'scope': 'scope3', 'category': 'business_travel_air',
             'activity_name': 'Flight — Economy, long-haul',
             'fuel_or_activity_type': 'flight_economy_longhaul', 'co2e_factor': 0.10239,
             'unit': 'passenger-km', 'source': 'DEFRA 2024', 'year': 2024},
            {'scope': 'scope3', 'category': 'business_travel_hotel',
             'activity_name': 'Hotel stay — India average',
             'fuel_or_activity_type': 'hotel_ind', 'co2e_factor': 40.6,
             'unit': 'room-night', 'source': 'Cornell CHSB 2023', 'year': 2023},
            {'scope': 'scope3', 'category': 'business_travel_car',
             'activity_name': 'Car rental — average',
             'fuel_or_activity_type': 'car_rental', 'co2e_factor': 0.15,
             'unit': 'km', 'source': 'DEFRA 2024', 'year': 2024},
            {'scope': 'scope3', 'category': 'business_travel_rail',
             'activity_name': 'Rail travel — average',
             'fuel_or_activity_type': 'rail', 'co2e_factor': 0.037,
             'unit': 'passenger-km', 'source': 'DEFRA 2024', 'year': 2024},
        ]

        for f in factors:
            EmissionFactor.objects.get_or_create(
                fuel_or_activity_type=f['fuel_or_activity_type'],
                source=f['source'],
                defaults={**f, 'tenant': None},
            )

    def _create_sap_sample(self, tenant, source, user):
        """Create sample SAP data."""
        from ingestion.normalization import normalize_sap_record

        batch = IngestionBatch.objects.create(
            tenant=tenant, data_source=source, status='completed',
            original_filename='sap_export_2024Q3.txt',
            total_rows=6, successful_rows=6, failed_rows=0, flagged_rows=2,
            quality_score=85.0, ingested_by=user,
        )

        sap_data = [
            {'mblnr': '4900000123', 'mjahr': '2024', 'zeile': '1', 'bwart': '201',
             'matnr': '0000000000FUEL001', 'maktx': 'Diesel Fuel', 'matkl': 'FUEL01',
             'werks': '1000', 'menge': '5000', 'meins': 'L', 'budat': '15.07.2024',
             'kostl': 'CC-MFG-01', 'anln1': '', 'aufnr': ''},
            {'mblnr': '4900000124', 'mjahr': '2024', 'zeile': '1', 'bwart': '201',
             'matnr': '0000000000FUEL002', 'maktx': 'Natural Gas', 'matkl': 'FUEL02',
             'werks': '2000', 'menge': '2.500,00', 'meins': 'KG', 'budat': '20.07.2024',
             'kostl': 'CC-MFG-02', 'anln1': '', 'aufnr': ''},
            {'mblnr': '4900000125', 'mjahr': '2024', 'zeile': '1', 'bwart': '201',
             'matnr': '0000000000FUEL003', 'maktx': 'Diesel (Vehicle Fleet)', 'matkl': 'FUEL01',
             'werks': '1000', 'menge': '1200', 'meins': 'L', 'budat': '22.07.2024',
             'kostl': 'CC-TRANS', 'anln1': 'ASSET-TRK-01', 'aufnr': ''},
            {'mblnr': '4900000126', 'mjahr': '2024', 'zeile': '1', 'bwart': '261',
             'matnr': '0000000000FUEL004', 'maktx': 'LPG Gas', 'matkl': 'FUEL03',
             'werks': '3000', 'menge': '800', 'meins': 'L', 'budat': '25.07.2024',
             'kostl': 'CC-PROD-01', 'anln1': '', 'aufnr': 'ORD-2024-001'},
            {'mblnr': '4900000127', 'mjahr': '2024', 'zeile': '1', 'bwart': '201',
             'matnr': '0000000000FUEL005', 'maktx': 'Gasoline (Unleaded)', 'matkl': 'FUEL04',
             'werks': '1000', 'menge': '3000', 'meins': 'GAL', 'budat': '2024-07-28',
             'kostl': 'CC-GEN', 'anln1': '', 'aufnr': ''},
            {'mblnr': '4900000128', 'mjahr': '2024', 'zeile': '1', 'bwart': '201',
             'matnr': '0000000000UNK99999', 'maktx': 'Unknown Chemical X-99', 'matkl': 'CHEM99',
             'werks': '1000', 'menge': '500', 'meins': 'KG', 'budat': '30.07.2024',
             'kostl': 'CC-LAB', 'anln1': '', 'aufnr': ''},
        ]

        for data in sap_data:
            raw = RawSAPRecord.objects.create(
                tenant=tenant, batch=batch, data_source=source,
                is_parsed=True, **data,
            )
            normalized = normalize_sap_record(raw, tenant)
            if normalized:
                normalized.save()

        self.stdout.write('  SAP sample: 6 records created')

    def _create_utility_sample(self, tenant, source, user):
        """Create sample utility data."""
        from ingestion.normalization import normalize_utility_record

        batch = IngestionBatch.objects.create(
            tenant=tenant, data_source=source, status='completed',
            original_filename='tata_power_export_jul2024.csv',
            total_rows=5, successful_rows=5, failed_rows=0, flagged_rows=1,
            quality_score=90.0, ingested_by=user,
        )

        utility_data = [
            {'account_number': 'ACCT-TP-1001', 'meter_number': 'MTR-001',
             'service_address': 'Plot 12, MIDC, Mumbai', 'rate_schedule': 'HT-1',
             'bill_start_date': '01/07/2024', 'bill_end_date': '31/07/2024',
             'consumption_kwh': '45600', 'demand_kw': '120',
             'meter_multiplier': '1.0', 'reading_type': 'actual', 'total_charge': '387600'},
            {'account_number': 'ACCT-TP-1002', 'meter_number': 'MTR-002',
             'service_address': 'Block C, Okhla, Delhi', 'rate_schedule': 'HT-2',
             'bill_start_date': '2024-06-28', 'bill_end_date': '2024-07-27',
             'consumption_kwh': '32100', 'demand_kw': '85',
             'meter_multiplier': '1.0', 'reading_type': 'actual', 'total_charge': '272850'},
            {'account_number': 'ACCT-TP-1003', 'meter_number': 'MTR-003',
             'service_address': 'Unit 5, Electronic City, Bangalore', 'rate_schedule': 'LT-5',
             'bill_start_date': '07/05/2024', 'bill_end_date': '07/07/2024',
             'consumption_kwh': '12400', 'demand_kw': '',
             'meter_multiplier': '1.0', 'reading_type': 'estimated', 'total_charge': '99200'},
            {'account_number': 'ACCT-TP-1001', 'meter_number': 'MTR-001',
             'service_address': 'Plot 12, MIDC, Mumbai', 'rate_schedule': 'HT-1',
             'bill_start_date': '01/06/2024', 'bill_end_date': '30/06/2024',
             'consumption_kwh': '42300', 'demand_kw': '115',
             'meter_multiplier': '1.0', 'reading_type': 'actual', 'total_charge': '359550'},
            {'account_number': 'ACCT-TP-1004', 'meter_number': 'MTR-004',
             'service_address': 'Warehouse 9, Peenya, Bangalore', 'rate_schedule': 'HT-1',
             'bill_start_date': '2024-07-01', 'bill_end_date': '2024-07-31',
             'consumption_kwh': '68000', 'demand_kw': '200',
             'meter_multiplier': '40', 'reading_type': 'actual', 'total_charge': '612000'},
        ]

        for data in utility_data:
            raw = RawUtilityRecord.objects.create(
                tenant=tenant, batch=batch, data_source=source,
                is_parsed=True, **data,
            )
            normalized = normalize_utility_record(raw, tenant)
            if normalized:
                normalized.save()

        self.stdout.write('  Utility sample: 5 records created')

    def _create_travel_sample(self, tenant, source, user):
        """Create sample travel data."""
        from ingestion.normalization import normalize_travel_record

        batch = IngestionBatch.objects.create(
            tenant=tenant, data_source=source, status='completed',
            original_filename='concur_itinerary_export_2024Q3.json',
            total_rows=8, successful_rows=8, failed_rows=0, flagged_rows=3,
            quality_score=75.0, ingested_by=user,
        )

        travel_data = [
            # Air segments
            {'trip_id': 'TRIP-2024-001', 'segment_type': 'Air', 'employee_id': 'EMP-1001',
             'origin_code': 'BOM', 'destination_code': 'DEL', 'cabin_class': 'economy',
             'airline_code': '6E', 'travel_date': '2024-07-10', 'distance_miles': '705.3'},
            {'trip_id': 'TRIP-2024-002', 'segment_type': 'Air', 'employee_id': 'EMP-1002',
             'origin_code': 'DEL', 'destination_code': 'SIN', 'cabin_class': 'business',
             'airline_code': 'AI', 'travel_date': '2024-07-15', 'distance_miles': ''},
            {'trip_id': 'TRIP-2024-003', 'segment_type': 'Air', 'employee_id': 'EMP-1003',
             'origin_code': 'BLR', 'destination_code': 'FRA', 'cabin_class': '',
             'airline_code': 'LH', 'travel_date': '2024-07-22', 'distance_miles': ''},
            # Hotel segments
            {'trip_id': 'TRIP-2024-002', 'segment_type': 'Hotel', 'employee_id': 'EMP-1002',
             'hotel_city': 'Singapore', 'hotel_country': 'SGP', 'nights': 3,
             'travel_date': '2024-07-15', 'origin_code': '', 'destination_code': '',
             'cabin_class': '', 'airline_code': '', 'distance_miles': ''},
            {'trip_id': 'TRIP-2024-003', 'segment_type': 'Hotel', 'employee_id': 'EMP-1003',
             'hotel_city': 'Frankfurt', 'hotel_country': 'DEU', 'nights': 5,
             'travel_date': '2024-07-22', 'origin_code': '', 'destination_code': '',
             'cabin_class': '', 'airline_code': '', 'distance_miles': ''},
            # Car segments
            {'trip_id': 'TRIP-2024-004', 'segment_type': 'Car', 'employee_id': 'EMP-1004',
             'car_type': 'SUV', 'car_fuel_type': '', 'distance_km': '',
             'travel_date': '2024-07-18', 'origin_code': '', 'destination_code': '',
             'cabin_class': '', 'airline_code': '', 'hotel_city': '', 'hotel_country': '',
             'nights': None, 'distance_miles': ''},
            {'trip_id': 'TRIP-2024-005', 'segment_type': 'Car', 'employee_id': 'EMP-1005',
             'car_type': 'Compact', 'car_fuel_type': 'Gasoline', 'distance_km': '250',
             'travel_date': '2024-07-20', 'origin_code': '', 'destination_code': '',
             'cabin_class': '', 'airline_code': '', 'hotel_city': '', 'hotel_country': '',
             'nights': None, 'distance_miles': ''},
            # Rail segment
            {'trip_id': 'TRIP-2024-006', 'segment_type': 'Rail', 'employee_id': 'EMP-1006',
             'origin_code': '', 'destination_code': '', 'distance_km': '450',
             'travel_date': '2024-07-25', 'cabin_class': '', 'airline_code': '',
             'hotel_city': '', 'hotel_country': '', 'nights': None,
             'car_type': '', 'car_fuel_type': '', 'distance_miles': ''},
        ]

        for data in travel_data:
            raw = RawTravelRecord.objects.create(
                tenant=tenant, batch=batch, data_source=source,
                is_parsed=True, raw_segment_data=data, **data,
            )
            normalized = normalize_travel_record(raw, tenant)
            if normalized:
                normalized.save()

        self.stdout.write('  Travel sample: 8 records created')
