
from django.template.response import TemplateResponse

# Api specific
from API.v3.resources.model_resources import *
from API.v3.resources.activity_view_resources import *
import json
from django.db import connection
from django.http import HttpResponse
from geodata.data_backup.country_data import countryData

def docs_index(request):
    context = dict()
    context['title'] = 'Documentation'
    t = TemplateResponse(request, 'base.html', context)
    return t.render()

def docs_start(request):
    context = dict()
    context['title'] = 'Getting started'
    t = TemplateResponse(request, 'documentation/start.html', context)
    return t.render()

def docs_resources(request):
    context = dict()
    context['title'] = 'Resources'
    context['resources'] = dict(
        organisation = OrganisationResource.__name__,
        organisation_doc = OrganisationResource.__doc__,
        activity = ActivityResource.__name__,
        activity_doc = ActivityResource.__doc__,
        country = CountryResource.__name__,
        country_doc = CountryResource.__doc__,
        region = RegionResource.__name__,
        region_doc = RegionResource.__doc__,
        sector = SectorResource.__name__,
        sector_doc = SectorResource.__doc__,
    )
    t = TemplateResponse(request, 'documentation/resources.html', context)
    return t.render()

def docs_filtering(request):
    context = dict()
    context['title'] = 'Filtering'
    t = TemplateResponse(request, 'documentation/filtering.html', context)
    return t.render()

def docs_ordering(request):
    context = dict()
    context['title'] = 'Ordering'
    t = TemplateResponse(request, 'documentation/ordering.html', context)
    return t.render()

def docs_about(request):
    context = dict()
    context['title'] = 'About'
    t = TemplateResponse(request, 'documentation/about.html', context)
    return t.render()




def make_where_query(values, name):
    query = ''
    if values:
        if not values[0]:
            return None

        for v in values:
            query += '  ' + name + ' = "' + v +'" OR'
        query = query[:-2]
    return query

def get_and_query(request, parameter, queryparameter):

    filters = request.GET.get(parameter, None)
    if filters:
        query = make_where_query(values=filters.split(','), name=queryparameter)
        query += ') AND ('
    else:
        query = ''
    return query

def get_fields(cursor):
    desc = cursor.description
    results = [
    dict(zip([col[0] for col in desc], row))
    for row in cursor.fetchall()
    ]
    return results

def get_filter_query(filters):
    q= ''

    for f in filters:
        if f[f.keys()[0]]:
            values = f[f.keys()[0]].split(',')
        else:
            values = None
        q += make_where_query(values=values, name=f.keys()[0]) + ') and ('

    q = q.replace(' and ()', '')
    q = q[:-5]
    q = " AND (" + q
    try:
        q[8]
        return q
    except IndexError:
        return ''

def find_polygon(iso2):
    polygon = None
    for k in countryData['features']:
        try:
            if k['properties']['iso2'] == iso2:
                polygon = k['geometry']
        except KeyError:
            pass
    if not polygon:
        polygon = {
            "type" : "Polygon",
            "coordinates" : []
        }


    return polygon



def activity_filter_options(request):
    cursor = connection.cursor()
    q_organisations = get_and_query(request, 'reporting_organisation__in', 'a.reporting_organisation_id')
    if ') AND (' in q_organisations:
        q_organisations = q_organisations[:-7]
        q_organisations = " AND " + q_organisations

    if q_organisations:
        cursor.execute('SELECT DISTINCT s.code as sector_id, s.name as sector_name, c.code as country_id, c.name as country_name, r.code as region_id, r.name as region_name  '\
                       'FROM IATI_activity a '\
                       'LEFT JOIN IATI_activity_recipient_region ir ON a.id = ir.activity_id '\
                       'LEFT JOIN geodata_region r ON r.code = ir.region_id '\
                       'LEFT JOIN IATI_activity_recipient_country ic ON a.id = ic.activity_id '\
                       'LEFT JOIN geodata_country c ON ic.country_id = c.code '\
                       'LEFT JOIN IATI_activity_sector ias ON a.id = ias.activity_id '\
                       'LEFT JOIN IATI_sector s ON ias.sector_id = s.code '\
                       'WHERE 1 %s' % (q_organisations))
        results = get_fields(cursor=cursor)



        options = {}
        options['countries'] = {}
        options['regions'] = {}
        options['sectors'] = {}

        for r in results:

            if r['country_name']:
                options['countries'][r['country_id']] = r['country_name']
            if r['sector_name']:
                options['sectors'][r['sector_id']] = r['sector_name']
            if r['region_name']:
                options['regions'][r['region_id']] = r['region_name']

        return HttpResponse(json.dumps(options), mimetype='application/json')

    else:

        cursor.execute('SELECT DISTINCT c.code as country_id, c.name as country_name FROM geodata_country c')
        results1 = get_fields(cursor=cursor)
        cursor.execute('SELECT DISTINCT r.code as region_id, r.name as region_name FROM geodata_region r where source is null')
        results2 = get_fields(cursor=cursor)
        cursor.execute('SELECT DISTINCT s.code as sector_id, s.name as sector_name FROM IATI_sector s')
        results3 = get_fields(cursor=cursor)

        options = {}
        options['countries'] = {}
        options['regions'] = {}
        options['sectors'] = {}

        for r in results1:
            if r['country_name']:
                options['countries'][r['country_id']] = r['country_name']

        for r in results2:
            if r['region_name']:
                options['regions'][r['region_id']] = r['region_name']

        for r in results3:
            if r['sector_name']:
                options['sectors'][r['sector_id']] = r['sector_name']

        return HttpResponse(json.dumps(options), mimetype='application/json')



def indicator_country_data_response(request):

    country_q = get_and_query(request, 'countries__in', 'c.code')
    region_q = get_and_query(request, 'regions__in', 'dac_region_code')
    year_q = get_and_query(request, 'years__in', 'id.year')
    indicator_q = get_and_query(request, 'indicators__in', 'indicator_id')

    if not indicator_q:
        return HttpResponse(json.dumps("No indicator given"), mimetype='application/json')

    filter_string = '  (' + country_q + region_q + year_q + indicator_q + ')'

    if 'AND ()' in filter_string:
        filter_string = filter_string[:-6]

    cursor = connection.cursor()

    cursor.execute('SELECT da.id as indicator_id, da.friendly_label, da.type_data, c.name as country_name, '
                   'id.value, id.year, AsText(c.center_longlat) as loc, c.code as country_id '
                   'FROM indicators_indicator_data id '
                   'JOIN geodata_country c ON id.country_id = c.code '
                   'JOIN indicators_indicator da ON da.id = id.indicator_id WHERE %s' % (filter_string))
    cursor_max = connection.cursor()

    indicator_q = indicator_q.replace(" ) AND (", "")
    cursor_max.execute('SELECT max(value) as max_value FROM indicators_indicator_data WHERE %s' % indicator_q)
    result_max = cursor_max.fetchone()
    desc = cursor.description
    results = [
    dict(zip([col[0] for col in desc], row))
    for row in cursor.fetchall()
    ]
    country = {}
    for r in results:

        try:
            country[r['country_id']]['years']
        except:
            loc = r['loc']
            if loc:

                loc = loc.replace("POINT(", "")
                loc = loc.replace(")", "")
                loc_array = loc.split(" ")
                longitude = loc_array[0]
                latitude = loc_array[1]
            else:
                longitude = None
                latitude = None

            country[r['country_id']] = {'name' : r['country_name'], 'country_id' : r['country_id'], 'longitude' : longitude, 'latitude' : latitude, 'indicator_friendly' : r['friendly_label'], 'type_data' : r['type_data'] , 'indicator' : r['indicator_id'],  'years' : {}}

        year = {}
        year['y' + str(r['year'])] = r['value']
        country[r['country_id']]['years'].update(year)

    country['max_value'] = result_max[0]

    return HttpResponse(json.dumps(country), mimetype='application/json')


def indicator_city_data_response(request):

    city_q = get_and_query(request, 'cities__in', 'city_id')
    country_q = get_and_query(request, 'countries__in', 'c.code')
    region_q = get_and_query(request, 'regions__in', 'r.code')
    year_q = get_and_query(request, 'years__in', 'id.year')
    indicator_q = get_and_query(request, 'indicators__in', 'indicator_id')

    if not indicator_q:
        return HttpResponse(json.dumps("No indicator given"), mimetype='application/json')

    filter_string = '  (' + city_q + country_q + region_q + year_q + indicator_q + ')'

    if 'AND ()' in filter_string:
        filter_string = filter_string[:-6]

    cursor = connection.cursor()

    cursor.execute('SELECT da.id as indicator_id, da.friendly_label, da.type_data, ci.name as city_name, '
                   'c.name as country_name, id.value, id.year, AsText(ci.location) as loc, ci.id as city_id '
                   'FROM indicators_indicator_data id '
                   'JOIN geodata_city ci ON id.city_id = ci.id '
                   'JOIN geodata_country c ON ci.country_id = c.code '
                   'JOIN geodata_region r ON c.region_id = r.code '
                   'JOIN indicators_indicator da ON da.id = id.indicator_id WHERE %s' % (filter_string))


    cursor_max = connection.cursor()
    indicator_q = indicator_q.replace(" ) AND (", "")
    cursor_max.execute('SELECT max(value) as max_value FROM indicators_indicator_data WHERE %s' % indicator_q)
    result_max = cursor_max.fetchone()
    desc = cursor.description
    results = [
    dict(zip([col[0] for col in desc], row))
    for row in cursor.fetchall()
    ]
    city = {}
    for r in results:

        try:
            city[r['city_id']]['years']
        except:
            loc = r['loc']
            if loc:

                loc = loc.replace("POINT(", "")
                loc = loc.replace(")", "")
                loc_array = loc.split(" ")
                longitude = loc_array[0]
                latitude = loc_array[1]
            else:
                longitude = None
                latitude = None

            city[r['city_id']] = {'name' : r['city_name'], 'city_id' : r['city_id'], 'country_name' : r['country_name'], 'longitude' : longitude, 'latitude' : latitude, 'indicator_friendly' : r['friendly_label'], 'type_data' : r['type_data'] , 'indicator' : r['indicator_id'],  'years' : {}}

        year = {}
        year['y' + str(r['year'])] = r['value']
        city[r['city_id']]['years'].update(year)

    city['max_value'] = result_max[0]



    return HttpResponse(json.dumps(city), mimetype='application/json')




def indicator_region_data_response(request):

    country_q = get_and_query(request, 'cities__in', 'c.code')
    region_q = get_and_query(request, 'regions__in', 'dac_region_code')
    year_q = get_and_query(request, 'years__in', 'id.year')
    indicator_q = get_and_query(request, 'indicators__in', 'indicator_id')

    if not indicator_q:
        indicator_q = ' indicator_id = "population"'

    filter_string = '  (' + country_q + region_q + year_q + indicator_q + ')'

    if 'AND ()' in filter_string:
        filter_string = filter_string[:-6]

    cursor = connection.cursor()

    cursor.execute('SELECT da.id as indicator_id, da.friendly_label, da.type_data, c.name as country_name, c.dac_region_code, '
                   'c.dac_region_name, id.value, id.year, AsText(c.center_longlat) as loc, c.code as country_id '
                   'FROM indicators_indicator_data id '
                   'LEFT OUTER JOIN geodata_city c ON id.country_id = c.code '
                   'JOIN indicators_indicator da ON da.id = id.indicator_id WHERE %s' % (filter_string))
    cursor_max = connection.cursor()

    indicator_q = indicator_q.replace(" ) AND (", "")
    cursor_max.execute('SELECT max(value) as max_value FROM indicators_indicator_data WHERE %s' % indicator_q)
    result_max = cursor_max.fetchone()
    desc = cursor.description
    results = [
    dict(zip([col[0] for col in desc], row))
    for row in cursor.fetchall()
    ]
    country = {}
    for r in results:

        try:
            country[r['country_id']]['years']
        except:
            loc = r['loc']
            if loc:

                loc = loc.replace("POINT(", "")
                loc = loc.replace(")", "")
                loc_array = loc.split(" ")
                longitude = loc_array[0]
                latitude = loc_array[1]
            else:
                longitude = None
                latitude = None

            country[r['country_id']] = {'name' : r['country_name'], 'country_id' : r['country_id'], 'longitude' : longitude, 'latitude' : latitude, 'indicator_friendly' : r['friendly_label'], 'type_data' : r['type_data'] , 'indicator' : r['indicator_id'],  'years' : {}}

        year = {}
        year['y' + str(r['year'])] = r['value']
        country[r['country_id']]['years'].update(year)

    country['max_value'] = result_max[0]

    return HttpResponse(json.dumps(country), mimetype='application/json')



def indicator_region_filter_options(request):

    region_q = get_and_query(request, 'regions__in', 'region.code')
    indicator_q = get_and_query(request, 'indicators__in', 'i.indicator_id')


    filter_string = ' AND (' + region_q + indicator_q + ')'
    if 'AND ()' in filter_string:
        filter_string = filter_string[:-6]
    cursor = connection.cursor()
    cursor.execute('SELECT DISTINCT i.indicator_id ,ind.friendly_label,region.code as region_id, region.name as region_name '
                   'FROM indicators_indicator_data i '
                   'JOIN indicators_indicator ind ON i.indicator_id = ind.id '
                   'LEFT OUTER JOIN geodata_region region on i.region_id = region.code '
                   'WHERE 1 %s' % (filter_string))

    desc = cursor.description
    results = [
    dict(zip([col[0] for col in desc], row))
    for row in cursor.fetchall()
    ]

    regions = {}
    countries = {}
    indicators = {}
    jsondata = {}

    for r in results:

        region = {}
        if r['region_id']:
            region[r['region_id']] = r['region_name']
            regions.update(region)

        country = {}
        if r['country_id']:
            country[r['country_id']] = r['country_name']
            countries.update(country)

        indicator = {}
        if r['indicator_id']:
            indicator[r['indicator_id']] = r['friendly_label']
            indicators.update(indicator)

    jsondata['regions'] = regions
    jsondata['countries'] = countries
    jsondata['indicators'] = indicators

    return HttpResponse(json.dumps(jsondata), mimetype='application/json')


def indicator_country_filter_options(request):

    country_q = get_and_query(request, 'countries__in', 'country.code')
    region_q = get_and_query(request, 'regions__in', 'region.code')
    indicator_q = get_and_query(request, 'indicators__in', 'i.indicator_id')


    filter_string = ' AND (' + country_q + region_q + indicator_q + ')'
    if 'AND ()' in filter_string:
        filter_string = filter_string[:-6]
    cursor = connection.cursor()
    cursor.execute('SELECT DISTINCT i.indicator_id, ind.friendly_label, country.code as country_id, country.name as country_name, region.code as region_id, region.name as region_name '
                   'FROM indicators_indicator_data i '
                   'JOIN indicators_indicator ind ON i.indicator_id = ind.id '
                   'LEFT OUTER JOIN geodata_country country on i.country_id = country.code '
                   'LEFT OUTER JOIN geodata_region region on country.region_id = region.code '
                   'WHERE 1 %s' % (filter_string))

    desc = cursor.description
    results = [
    dict(zip([col[0] for col in desc], row))
    for row in cursor.fetchall()
    ]

    regions = {}
    countries = {}
    indicators = {}
    jsondata = {}

    for r in results:

        region = {}
        if r['region_id']:
            region[r['region_id']] = r['region_name']
            regions.update(region)

        country = {}
        if r['country_id']:
            country[r['country_id']] = r['country_name']
            countries.update(country)

        indicator = {}
        if r['indicator_id']:
            indicator[r['indicator_id']] = r['friendly_label']
            indicators.update(indicator)

    jsondata['regions'] = regions
    jsondata['countries'] = countries
    jsondata['indicators'] = indicators

    return HttpResponse(json.dumps(jsondata), mimetype='application/json')



def indicator_city_filter_options(request):

    city_q = get_and_query(request, 'cities__in', 'city.id')
    country_q = get_and_query(request, 'countries__in', 'country.code')
    region_q = get_and_query(request, 'regions__in', 'region.code')
    indicator_q = get_and_query(request, 'indicators__in', 'i.indicator_id')

    filter_string = ' AND (' + city_q + country_q + region_q + indicator_q + ')'
    if 'AND ()' in filter_string:
        filter_string = filter_string[:-6]
    cursor = connection.cursor()
    cursor.execute('SELECT DISTINCT i.indicator_id ,ind.friendly_label, city.id as city_id, city.name as city_name, country.code as country_id, country.name as country_name, region.code as region_id, region.name as region_name '
                   'FROM indicators_indicator_data i '
                   'JOIN indicators_indicator ind ON i.indicator_id = ind.id '
                   'LEFT OUTER JOIN geodata_city city ON i.city_id=city.id '
                   'LEFT OUTER JOIN geodata_country country on city.country_id = country.code '
                   'LEFT OUTER JOIN geodata_region region on country.region_id = region.code '
                   'WHERE 1 %s' % (filter_string))

    desc = cursor.description
    results = [
    dict(zip([col[0] for col in desc], row))
    for row in cursor.fetchall()
    ]

    regions = {}
    countries = {}
    cities = {}
    indicators = {}
    jsondata = {}

    for r in results:

        region = {}
        if r['region_id']:
            region[r['region_id']] = r['region_name']
            regions.update(region)

        country = {}
        if r['country_id']:
            country[r['country_id']] = r['country_name']
            countries.update(country)

        city = {}
        if r['city_id']:
            city[r['city_id']] = r['city_name']
            cities.update(city)

        indicator = {}
        if r['indicator_id']:
            indicator[r['indicator_id']] = r['friendly_label']
            indicators.update(indicator)

    jsondata['regions'] = regions
    jsondata['countries'] = countries
    jsondata['cities'] = cities
    jsondata['indicators'] = indicators

    return HttpResponse(json.dumps(jsondata), mimetype='application/json')




def country_geojson_response(request):

    country_q = get_and_query(request, 'countries__in', 'c.code')
    budget_q = request.GET.get('budgets__in', None)
    region_q = get_and_query(request, 'regions__in', 'r.code')
    sector_q = get_and_query(request, 'sectors__in', 's.sector_id')
    organisation_q = get_and_query(request, 'reporting_organisation__in', 'a.reporting_organisation_id')

    filter_string = ' AND (' + country_q + organisation_q + region_q + sector_q + ')'
    if 'AND ()' in filter_string:
        filter_string = filter_string[:-6]

    if budget_q:
        filter_string += ' AND total_budget > ' + budget_q

    if region_q:
        filter_region = 'LEFT JOIN IATI_activity_recipient_region rr ON rr.activity_id = a.id LEFT JOIN geodata_region r ON rr.region_id = r.code '
    else:
        filter_region = ''

    if sector_q:
        filter_sector = 'LEFT JOIN IATI_activity_sector s ON a.id = s.activity_id '
    else:
        filter_sector = ''

    cursor = connection.cursor()
    query = 'SELECT c.code as country_id, c.name as country_name, count(a.id) as total_projects '\
            'FROM IATI_activity a '\
            'LEFT JOIN IATI_activity_recipient_country rc ON rc.activity_id = a.id '\
            'LEFT JOIN geodata_country c ON rc.country_id = c.code '\
            '%s %s'\
            'WHERE 1 %s'\
            'GROUP BY c.code %s' % (filter_region, filter_sector, filter_string)
    cursor.execute(query)

    activity_result = {'type' : 'FeatureCollection', 'features' : []}

    activities = []

    results = get_fields(cursor=cursor)
    for r in results:
        country = {}
        country['type'] = 'Feature'
        country['id'] = r['country_id']

        country['properties'] = {'name' : r['country_name'], 'project_amount' : r['total_projects']}
        country['geometry'] = find_polygon(r['country_id'])

        activities.append(country)

    result = {}

    activity_result['features'] = activities
    return HttpResponse(json.dumps(activity_result), mimetype='application/json')





def adm1_region_geojson_response(request):

    country_id = request.GET.get("country_id", None)

    cursor = connection.cursor()

    cursor.execute('SELECT r.adm1_code, r.name, r.polygon, r.geometry_type  '\
            'FROM geodata_adm1_region r '\
            'WHERE r.country_id = "%s"' % (country_id))

    activity_result = {'type' : 'FeatureCollection', 'features' : []}

    activities = []

    results = get_fields(cursor=cursor)
    for r in results:
        region = {}
        region['type'] = 'Feature'
        region['geometry'] = {'type' : r['geometry_type'], 'coordinates' : r['polygon']}
        region['properties'] = {'id' : r['adm1_code'], 'name' : r['name']}
        activities.append(region)

    result = {}

    activity_result['features'] = activities
    return HttpResponse(json.dumps(activity_result), mimetype='application/json')