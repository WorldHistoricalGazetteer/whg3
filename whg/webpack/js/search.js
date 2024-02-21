// /whg/webpack/search.js

import Dateline from './dateline';
import throttle from 'lodash/throttle';
import debounce from 'lodash/debounce';
import {
  geomsGeoJSON,
} from './utilities';
import {
  ccode_hash,
} from '../../../static/js/parents';
import {
  CountryCacheFeatureCollection,
} from './countryCache';
import '../css/typeahead.css';
import '../css/dateline.css';
import '../css/search.css';

let results = null;
let checkboxStates = {};
let draw;
let $drawControl;
let countryCache = new CountryCacheFeatureCollection();
let searchDisabled = false;
let enteringPortal = false;

let dateRangeChanged = throttle(() => { // Uses imported lodash function
  initiateSearch();
}, 300);

let mapParameters = {
  maxZoom: 8,
  fullscreenControl: true,
  downloadMapControl: true,
  drawingControl: {
    hide: true,
  },
  temporalControl: {
    fromValue: 800,
    toValue: 1800,
    minValue: -2000,
    maxValue: 2100,
    open: false,
    includeUndated: true, // null | false | true - 'false/true' determine state of select box input; 'null' excludes the button altogether
    epochs: null,
    automate: null,
    onChange: dateRangeChanged,
    onClick: initiateSearch,
  },
};
let mappy = new whg_maplibre.Map(mapParameters);

function waitMapLoad() {
  return new Promise((resolve) => {
    mappy.on('load', () => {
      console.log('Map loaded.');
      const style = mappy.getStyle();
      style.layers.forEach(layer => {
        if (layer.id.includes('label')) {
          mappy.setLayoutProperty(layer.id, 'visibility', 'none');
        }
      });

      if (has_areas) {
        mappy.newSource('userareas') // Add empty source
            .newLayerset('userareas', 'userareas', 'userareas');
      }

      mappy.newSource('countries') // Add empty source
          .newLayerset('countries', 'countries', 'countries');

      mappy.newSource('places') // Add empty source
          .newLayerset('places');

      function getFeatureId(e) {
        const features = mappy.queryRenderedFeatures(e.point);
        if (features.length > 0) {
          if (features[0].layer.id.startsWith('places_')) { // Query only the top-most feature
            mappy.getCanvas().style.cursor = 'pointer';
            return features[0].id;
          }
        }
        mappy.getCanvas().style.cursor = 'grab';
        return null;
      }

      mappy.on('mousemove', function(e) {
        getFeatureId(e);
      });

      mappy.on('click', function(e) {
        $('.result').
            eq(getFeatureId(e)).
            attr('data-map-clicked', 'true').
            click();
      });

      resolve();
    });
  });
}

function waitDocumentReady() {
  return new Promise((resolve) => {
    $(document).ready(() => resolve());
  });
}

Promise.all([
  waitMapLoad(),
  waitDocumentReady(),
  Promise.all(select2_CDN_fallbacks.map(loadResource))]).then(() => {

  const checkboxesContainer = $('#adv_checkboxes');
  adv_filters.forEach(filter => { // Construct advanced search filters
    const [value, label] = filter;
    const checkboxContainer = $('<p>');
    const checkboxInput = $('<input>', {
      type: 'checkbox',
      id: `cb_${value.toLowerCase()}`,
      value: value,
      checked: true,
    });
    const checkboxLabel = $('<label>', {
      for: `cb_${value.toLowerCase()}`,
    }).text(` ${label} (${value})`);
    checkboxContainer.append(checkboxInput, checkboxLabel);
    checkboxesContainer.append(checkboxContainer);
  });
  $('#adv_filters script').remove(); // Remove `adv_filters` from the DOM

  draw = mappy._draw;
  $drawControl = $(mappy._drawControl);

  // Delegated event listener for Portal links
  $(document).on('click', '.portal-link', function(e) {
    e.preventDefault();
    e.stopPropagation();

    const pid = $(this).data('pid');
    const children = $(this).data('children') ?
        decodeURIComponent($(this).data('children')).
            split(',').
            map(id => parseInt(id, 10)) : [];
    const placeIds = [pid, ...children].filter(
        id => !isNaN(id) && id !== null && id !== undefined);
    const csrfToken = getCookie('csrftoken');

    console.log('pid', pid);
    console.log('children', $(this).attr('data-children'));
    console.log('placeIds', placeIds);
    console.log('csrfToken', csrfToken);

    $.ajax({
      url: '/places/set-current-result/',
      type: 'POST',
      data: {
        'place_ids': placeIds,
        'csrfmiddlewaretoken': csrfToken,
      },
      traditional: true,
      success: function(response) {
        if(children.length > 0) {
          console.log('Entering portal with children', children);
          enteringPortal = true;
          window.location.href = '/places/portal/';
        } else {
          console.log('no children, going to detail page');
          enteringPortal = true; // not really; setting flag to prevent clearing of last search
          window.location.href = `/places/${pid}/detail`;
        }
      },
      error: function(xhr, status, error) {
        console.error('AJAX POST error:', error);
      },
    });

  });
  // END Ids to session

  // Delegated event listener for Result links
  $(document).on('click', '.result', function(e) {

    const index = $(this).index(); // Get index of clicked card

    mappy.removeFeatureState({
      source: 'places',
    });
    mappy.setFeatureState({
      source: 'places',
      id: index,
    }, {
      highlight: true,
    });

    const featureCollection = mappy.getSource('places')._data;

    if ($(this).attr('data-map-clicked') === 'true') { // Scroll table
      $(this).removeAttr('data-map-clicked');
      const $container = $('#result_container');
      $container.scrollTop($(this).offset().top - $container.offset().top);
    } else if ($(this).attr('data-map-initialising') === 'true') {
      $(this).removeAttr('data-map-initialising');
      mappy.fitBounds(bbox(featureCollection), {
        padding: 30,
        // maxZoom: 5,
        duration: 1000,
      });
    } else {
      mappy.flyTo({ // Adjust map
        center: centroid(
            featureCollection.features[index]).geometry.coordinates,
        duration: 1000,
      });
    }

    $('.result').removeClass('selected');
    $(this).addClass('selected');

  });

  // Delegated event listener for togglable links
  $(document).on('click', '.toggleControl', function(e) {
    e.stopPropagation(); // Prevent click from acting on parent elements
    e.preventDefault();
    const $toggleTarget = $(e.target).siblings('.toggleTarget');
    $toggleTarget.toggle();
    $(e.target).text($toggleTarget.is(':visible') ? 'view fewer' : 'view all');
  });

  function updateAreaMap() {
    const countries = $('#countryDropdown').
        select2('data').
        map(country => country.id);
    countryCache.filter(countries).then(filteredCountries => {
      mappy.getSource('countries').setData(filteredCountries);

      try {
        mappy.fitBounds(bbox(filteredCountries), {
          padding: 30,
          maxZoom: 7,
          duration: 1000,
        });
      } catch {
        mappy.reset();
      }
    });
  }

  const debouncedUpdates = debounce(() => { // Uses imported lodash function
    updateAreaMap();
  }, 400);

  const countryDropdown = $('#countryDropdown');
  countryDropdown.select2({
    data: dropdown_data,
    width: 'element', // Use CSS rules
    placeholder: $(this).data('placeholder'),
    closeOnSelect: false,
    allowClear: false,
  }).on('select2:selecting', function(e) {
    if (!!e.params.args.data['ccodes']) { // Region selected: add countries from its ccodes
      e.preventDefault();
      let ccodes = Array.from(new Set([
        ...e.params.args.data['ccodes'],
        ...countryDropdown.select2('data').map(country => country.id)]));
      countryDropdown.val(ccodes).trigger('change');
    }
  }).on('change', function(e) {
    if (!searchDisabled) {
      flashSearchButton();
      debouncedUpdates();
    }
  });

  $('#clearCountryDropdown').on('click', function() {
    countryDropdown.val(null).trigger('change');
  });

  if (has_areas) { // Element will not be present if user is not logged in, or has no study areas defined
    const userAreaDropdown = $('#userAreaDropdown');
    userAreaDropdown.select2({
      data: user_areas.map(feature => ({
        id: feature.properties.id,
        text: feature.properties.title,
        feature: feature,
      })),
      width: 'element', // Use CSS rules
      placeholder: $(this).data('placeholder'),
      closeOnSelect: false,
      allowClear: false,
    }).on('change', function(e) {
      if (!searchDisabled) flashSearchButton();
      mappy.getSource('userareas').setData({
        type: 'FeatureCollection',
        features: userAreaDropdown.select2('data').
            map(feature => feature.feature),
      });
    });

    $('#clearUserAreaDropdown').on('click', function() {
      userAreaDropdown.val(null).trigger('change');
    });
  }

  var referringPage = document.referrer;
  if (referringPage) { // If arriving from `portal` or `home` pages, load and render any saved search+results
    if (referringPage.includes('/') || referringPage.includes('portal')) {
      const storedResults = localStorage.getItem('last_search'); // Includes both `.parameters` and `.suggestions` objects
      results = storedResults ? JSON.parse(storedResults) : results;
    } else { // otherwise clear any previous search+results from LocalStorage
      console.log('Clearing last search from localStorage');
      localStorage.removeItem('last_search');
    }
  }
  $(window).on('beforeunload', function(event) { // Clear any search+results if not navigating away to a portal page
    if (!enteringPortal) {
      localStorage.removeItem('last_search');
    }
  });

  if (results) {
    renderResults(results, true); // Pass a `true` flag to indicate that results are from storage
  } else {
    // Initialise default temporal control
    let datelineContainer = document.createElement('div');
    datelineContainer.id = 'dateline';
    document.querySelector('.maplibregl-control-container').
        appendChild(datelineContainer);
    window.dateline = new Dateline(mapParameters.temporalControl);
  }

  //$('#advanced_search').hide();

  function initialiseSuggestions() { // based on search mode
    var suggestions = new Bloodhound({ // https://github.com/twitter/typeahead.js/blob/master/doc/bloodhound.md#remote
      datumTokenizer: Bloodhound.tokenizers.whitespace,
      queryTokenizer: Bloodhound.tokenizers.whitespace,
      local: [],
      indexRemote: false,
      remote: {
        url: '/search/suggestions/?q=%QUERY&mode=' + $('#search_mode').val(),
        wildcard: '%QUERY',
        rateLimitBy: 'debounce',
        rateLimitWait: 100,
      },
    });

    $('#search_input').typeahead('destroy').typeahead({ // https://github.com/twitter/typeahead.js/blob/master/doc/jquery_typeahead.md
      highlight: true,
      hint: true,
      minLength: 3,
    }, {
      name: 'Places',
      source: suggestions.ttAdapter(),
    }).on('typeahead:select', function(e, item) {
      $(this).val(item);
      toggleButtonState();
    });

    return suggestions;
  }

  initialiseSuggestions();
  $('#search_mode').on('change', function() {
    initialiseSuggestions();
  });

  $('#search_input').on('keyup', function(event) { // Allow [Enter] key to initiate search
    if (event.which === 13) {
      event.preventDefault();
      $('#initiate_search').focus();
      initiateSearch();
    }
  });

  $('#clear_search').on('click', function() { // Clear the input, results, and map
    if (!$(this).hasClass('disabledButton')) clearResults();
  });

  $('#initiate_search').on('click', function() {
    if (!$(this).hasClass('disabledButton')) initiateSearch();
  });

  $('#check_select').on('click', () => {
    $('#adv_checkboxes input').prop('checked', true);
    flashSearchButton();
  });

  $('#check_clear').on('click', () => {
    $('#adv_checkboxes input').prop('checked', false);
    flashSearchButton();
  });

  // START Ids to session (kg 2023-10-31)
  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  mappy.on('draw.create', initiateSearch); // draw events fail to register if not done individually
  mappy.on('draw.delete', initiateSearch);
  mappy.on('draw.update', initiateSearch);

  $('#adv_checkboxes input, #search_mode, #countryDropdown').change(function() {
    flashSearchButton();
  });

  $('#search_input').on('input', function() {
    flashSearchButton();
    toggleButtonState();
  });
  toggleButtonState();

  $('.accordion-button').each(function() { // Initialise Filter Accordions
    var accordion = $($(this).data('bs-target'));
    var accordionHeader = accordion.siblings('.accordion-header');
    var chevron = accordionHeader.find('.accordion-toggle-indicator i');
    accordionHeader.on('click', function() {
      chevron.toggleClass('fa-chevron-up fa-chevron-down');
      accordion.collapse('toggle');
    });
  });

}).catch(error => console.error('An error occurred:', error));

// $(window).resize(function() {
//   if ($('#result_facets').height() > someValue) { // Replace someValue with the maximum height you want for #result_facets
//     $('#detail').collapse('hide');
//   } else {
//     $('#detail').collapse('show');
//   }
// }).resize(); // Trigger the resize event initially

function toggleButtonState() {
  const disable = $('#search_input').val().trim() == '';
  $('#initiate_search, #clear_search').each(function() {
    $(this)
        //.prop('disabled', disable) // Cannot use this because it disables the title
        .toggleClass('disabledButton', disable).
        attr('title', $(this).data('title').split('|')[disable ? 1 : 0]).
        attr('aria-label', $(this).data('title').split('|')[disable ? 1 : 0]);
  });
}

function flashSearchButton(toggle = true) {
  $('#initiate_search').
      toggleClass('flashing', toggle).
      attr('title', toggle ? 'Update search results' : 'Initiate search');
}

function clearResults() { // Reset all inputs to default values
  searchDisabled = true;
  $('#search_mode').val('exactly');
  $('#search_input').typeahead('close');
  $('#search_input').val('');
  $('#result_facets input[type="checkbox"]').prop('checked', false);
  $('#adv_checkboxes input').prop('checked', true);
  window.dateline.reset(mapParameters.temporalControl.fromValue,
      mapParameters.temporalControl.toValue,
      mapParameters.temporalControl.open);
  draw.deleteAll();
  mappy.getSource('places').setData(mappy.nullCollection());
  mappy.reset();
  $('#countryDropdown').val(null).trigger('change');
  $('#userAreaDropdown').val(null).trigger('change'); // Ignored if not present
  mappy.getSource('countries').setData(mappy.nullCollection());
  $('#search_content').toggleClass('no-results', true);
  $('#search_content').toggleClass('no-filtered-results', false);
  $('#search_results').empty();
  localStorage.removeItem('last_search');
  searchDisabled = false;
  flashSearchButton(false);
  toggleButtonState();

}

function renderResults(data, fromStorage = false) {

  let $resultsDiv = $('#search_results');
  $resultsDiv.empty();
  $('#search_content').toggleClass('initial', false);
  $('#search_content').toggleClass('no-filtered-results', false);

  if (fromStorage) { // Initialise by setting all inputs to retrieved values
    $('#search_mode').val(data.parameters.mode);
    $('#search_input').val(data.parameters.qstr);
    $('#result_facets input[type="checkbox"]').prop('checked', false);

    const checkedOptions = data.parameters.fclasses.toLowerCase().split(',');
    $('#adv_checkboxes input').each(function(index, checkbox) {
      $(checkbox).
          prop('checked',
              checkedOptions.includes($(checkbox).attr('id').split('_')[1]));
    });

    // Initialise temporal control
    let datelineContainer = document.createElement('div');
    datelineContainer.id = 'dateline';
    document.querySelector('.maplibregl-control-container').
        appendChild(datelineContainer);
    window.dateline = new Dateline({
      ...mapParameters.temporalControl,
      fromValue: data.parameters.start == '' ?
          mapParameters.temporalControl.fromValue :
          data.parameters.start,
      toValue: data.parameters.end == '' ?
          mapParameters.temporalControl.toValue :
          data.parameters.end,
      open: data.parameters.temporal,
      includeUndated: data.parameters.undated,
    });

    // Initialise drawing
    if (!!data.parameters.bounds && data.parameters.bounds.geometries.length >
        0) {
      data.parameters.bounds.geometries.forEach(geometry => {
        draw.add(geometry);
      });
    }

    if (data.parameters.countries !== null) {
      searchDisabled = true; // Prevent zoom to selected countries
      $('#countryDropdown').val(data.parameters.countries).trigger('change');
      countryCache.filter(data.parameters.countries).then(filteredCountries => {
        mappy.getSource('countries').setData(filteredCountries);
      });
      searchDisabled = false;
    }

    if (data.parameters.userareas !== null) {
      searchDisabled = true; // Prevent flashSearchButton()
      $('#userAreaDropdown').val(data.parameters.userareas).trigger('change');
      searchDisabled = false;
    }
  }

  let featureCollection = data.features ?
      data :
      geomsGeoJSON(data['suggestions']); // `data` may already be a FeatureCollection

  results = featureCollection.features;

  // Update Results
  $('#search_content').toggleClass('no-results', results.length == 0); // CSS hides #search_results, #result_facets

  results.forEach(feature => {
    let result = feature.properties;
    const count = parseInt(result.linkcount) + 1;
    const pid = result.pid;
    const whg_id = result.whg_id;
    const children = result.children;
    const encodedChildren = encodeURIComponent(children.join(','));

    let resultIdx = result.index.startsWith('whg') ? 'whg' : 'pub';
    // Aberaeron (in 'pub' and 'whg') will have two cards, one for each index
    let html = `<div class="result ${resultIdx}-result">
	    <span>
	      <span class="red-head">${result.title}</span> 
	      <span class="float-end small">(${resultIdx === 'pub' ? 'unlinked record' : (count > 1 ?
            `${count} linked records <i class="fas fa-link"></i>` : 'unlinked record')})
	          <a href="#" class="ms-2 portal-link" data-pid="${pid}" data-children="${encodedChildren}">
						${resultIdx === 'whg' ? 'place portal' : 'place detail'}</a>
	      </span>
	    </span>`;

    if (result.variants && result.variants.length > 0) {
      const threshold = 12;
      const limitedVariants = result.variants.slice(0, threshold).join(', ');
      const allVariants = result.variants.join(', ');

      html += `
		        <p>Variants (${result.variants.length}):
		            ${result.variants.length > threshold ?
          `<a href="#" class="toggleControl ms-2 italic">view all</a><br/>` :
          ''}
		            <span>${limitedVariants}</span>
		            ${result.variants.length > threshold ?
          `<span class="toggleTarget" style="display:none">${allVariants}</span>` :
          ''}
		        </p>
		    `;
    } else {
      html += `<p>Variants: none provided</p>`;
    }

    html += (result.types && result.types.length > 0) ?
        `<p>Type(s): ${result.types.join(', ')}</p>` :
        '';
    html += (result.ccodes && result.ccodes.length > 0) ?
        `<p>Country Codes: ${result.ccodes.join(', ')}</p>` :
        '';
    html += (result.fclasses && result.fclasses.length > 0) ?
        `<p>Feature Classes: ${result.fclasses.join(', ')}</p>` :
        '';
    html += (result.types && result.types.length > 0) ?
        `<p>Types: ${result.types.join(', ')}</p>` :
        '';

    html += `</div>`;
    $resultsDiv.append(html);
  });

  // Update Map & Detail with first result (if any)
  mappy.getSource('places').setData(featureCollection);
  $drawControl.toggle(results.length > 0 || draw.getAll().features.length > 0); // Leave control to allow deletion of areas

  if (fromStorage || results.length > 0) {
    // Highlight first result and render its detail
    $('.result').first().attr('data-map-initialising', 'true').click();
  } else {
    mappy.reset();
    $('#detail').empty(); // Clear the detail view
  }

  buildResultFilters();

}

function buildResultFilters() {

  const {
    typesSet,
    typeCounts,
  } = results.reduce(({
                        typesSet,
                        typeCounts,
                      }, feature) => {
    const result = feature.properties;
    result.types.forEach(type => {
      typesSet.add(type);
      typeCounts[type] = (typeCounts[type] || 0) + 1;
    });
    return {
      typesSet,
      typeCounts,
    };
  }, {
    typesSet: new Set(),
    typeCounts: {},
  });

  const allTypes = Array.from(typesSet).sort();

  var typesShowing = $('#headingTypes').
      find('.accordion-toggle-indicator i').
      hasClass('fa-chevron-up');
  if ((allTypes.length <= 5 && !typesShowing) ||
      (allTypes.length > 5 && typesShowing)) {
    $('#headingTypes button').click();
  }

  $('#type_checkboxes').html(allTypes.map(type => {
    const count = typeCounts[type] || 0;
    return `
	    <p><input
	      type="checkbox"
	      id="type_${type.replace(' ', '_')}"
	      value="${type}"
	      class="filter-checkbox type-checkbox"
	      checked="${checkboxStates[type] || false}"
	    />
	    <label for="type_${type}">${type} (${count})</label></p>`;
  }).join(''));

  const {
    countriesSet,
    countryCounts,
  } = results.reduce(({
                        countriesSet,
                        countryCounts,
                      }, feature) => {
    const result = feature.properties;
    result.ccodes.forEach(country => {
      countriesSet.add(country);
      countryCounts[country] = (countryCounts[country] || 0) + 1;
    });
    return {
      countriesSet,
      countryCounts,
    };
  }, {
    countriesSet: new Set(),
    countryCounts: {},
  });

  const allCountries = Array.from(countriesSet).sort();

  var countriesShowing = $('#headingCountries').
      find('.accordion-toggle-indicator i').
      hasClass('fa-chevron-up');
  if ((allCountries.length <= 5 && !countriesShowing) ||
      (allCountries.length > 5 && countriesShowing)) {
    $('#headingCountries button').click();
  }

  $('#country_checkboxes').html(allCountries.map(country => {
    const cName = ccode_hash[country]['gnlabel'];
    const count = countryCounts[country] || 0;
    return `
	    <p><input
	      type="checkbox"
	      id="country_${country}"
	      value="${country}"
	      class="filter-checkbox country-checkbox"
	      checked="${checkboxStates[country] || false}"
	    />
	    <label for="country_${country}">${cName} (${country}; ${count})</label></p>`;
  }).join(''));

  $('#typesCount').text(`(${allTypes.length})`);
  $('#countriesCount').text(`(${allCountries.length})`);

  $('.filter-checkbox').change(function() {
    // store state
    checkboxStates[this.value] = this.checked;

    // Get all checked checkboxes
    let checkedTypes = $('.type-checkbox:checked').map(function() {
      return this.value;
    }).get();
    let checkedCountries = $('.country-checkbox:checked').map(function() {
      return this.value;
    }).get();

    const filteredResults = results.filter(feature => {
      const hasCommonType = feature.properties.types.some(
          type => checkedTypes.includes(type));
      const hasCommonCountry = feature.properties.ccodes.some(
          country => checkedCountries.includes(country));
      return hasCommonType && hasCommonCountry;
    });

    mappy.getSource('places').setData({
      type: 'FeatureCollection',
      features: filteredResults,
    });
    const $pidLinks = $('#result_container .portal-link');
    $pidLinks.each(function() {
      const show = filteredResults.some(
          feature => feature.properties.pid === $(this).data('pid'));
      $(this).closest('.result').toggle(show);
    });
    $('#search_content').
        toggleClass('no-filtered-results', filteredResults.length == 0);

  });

}

function initiateSearch() {

  if (searchDisabled) return;

  flashSearchButton(false);
  const options = gatherOptions();

  if (options.qstr == '') {
    console.log('Cannot search without an input place name.');
    return;
  }

  console.log('Initiating search...', options);

  // AJAX POST request to SearchView() with the options (includes qstr)
  $.ajax({
    type: 'POST',
    url: '/search/index/',
    data: JSON.stringify(options),
    contentType: 'application/json',
    headers: {
      'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
    }, // Include CSRF token in headers for Django POST requests
    success: function(data) {
      console.log('...search completed.', data);
      localStorage.setItem('last_search', JSON.stringify(data)); // Includes both `.parameters` and `.suggestions` objects
      renderResults(data);
    },
    error: function(error) {
      console.error('Error:', error);
    },
  });
}

function gatherOptions() { // gather and return option values from the UI

  const fclasses = $('#adv_checkboxes input:checked').map(function() {
    return $(this).val();
  }).get(); // .get() converts jQuery object to an array

  const areaFilter = {
    type: 'GeometryCollection',
    geometries: draw.getAll().features.map(feature => feature.geometry),
  };

  const options = {
    qstr: $('#search_input').val(),
    mode: $('#search_mode').val(),
    idx: eswhg, // hard-coded in `search.html` template
    fclasses: fclasses.join(','),
    temporal: window.dateline.open,
    start: window.dateline.open ? window.dateline.fromValue : '',
    end: window.dateline.open ? window.dateline.toValue : '',
    undated: window.dateline.open ? window.dateline.includeUndated : true,
    bounds: areaFilter,
    countries: $('#countryDropdown').select2('data').map(country => country.id),
    userareas: $('#userAreaDropdown').select2('data').map(feature => feature.id),
  };

  return options;
}
