// vis_parameters.js
// Imported through `builders.js`, but operates only on `place_collection_build.html` (which has a #configurationTable)

import '../css/vis_parameters.css';

$(document).ready(function() {
	
	const isPlaceCollection = $("#configurationTable").length > 0;
	if (isPlaceCollection) {
		
		console.log('Place Collection: vis_parameters:', vis_parameters);
	
		if (typeof vis_parameters === 'undefined' || Object.keys(vis_parameters).length === 0) {
			vis_parameters = {
				min: {
					tabulate: "initial",
					temporal_control: "filter",
					trail: false
				},
				max: {
					tabulate: false,
					temporal_control: "filter",
					trail: false
				},
				seq: {
					tabulate: false,
					temporal_control: "player",
					trail: true
				}
			};
			console.log('vis_parameters was undefined or empty, so set to default values:', vis_parameters);
		} else if (window.saved_settings) {
			vis_parameters = window.saved_settings;
			console.log('vis_parameters', vis_parameters);
		}
	
		generateConfigurationRows();

		// Add event listeners to all input elements to update vis_parameters and toggle controls
		$("#configurationTable").on("change", ".tabulate-checkbox", toggleControls);
		$("#configurationTable").on("change", "input, select", updateVisParameters);
		
		// Call toggleControls initially to set initial state
		toggleControls();
		
		$('#collection_form').on('submit', function() { // Update hidden Form value before submission
			$('#visParameters').val(JSON.stringify(vis_parameters));
		});
		
	}
});

// Function to generate the configuration table rows dynamically based on vis_parameters
function generateConfigurationRows() {

	// Dictionary to translate vis_parameters keys to labels
	const labelDictionary = {
		seq: "Sequence",
		min: "Start-date",
		max: "End-date"
	};
	
	// Dictionary to translate temporal_control values to options in dropdown menus
	const temporalControlOptions = {
		player: "Sequencer",
		filter: "Date Slider",
		null: "None"
	};
	
	const tbody = $("#configurationTable tbody");
	tbody.empty(); // Clear previous content

	for (const [attribute, config] of Object.entries(vis_parameters)) {
		const label = labelDictionary[attribute];
		const optionHTML = Object.entries(temporalControlOptions)
			.map(([value, text]) => `<option value="${value}">${text}</option>`)
			.join("");

		const tr = `
      <tr>
        <td style="text-align: right;">${label}:</td>
        <td><input type="checkbox" id="${attribute}" name="${attribute}Tabulate" class="tabulate-checkbox" title="Should this value be included in the tabulation of the dataset?" ${config.tabulate !== false ? "checked" : ""}></td>
        <td>
          <select name="${attribute}TemporalControl" class="control-select" title="Choose (or remove) a temporal control to be used when sorting the tabulated dataset on this value.">
            ${optionHTML}
          </select>
        </td>
        <td><input type="checkbox" id="${attribute}Trail" name="${attribute}Trail" class="trail-checkbox" title="Draw map-trails between consecutive features when sorting the tabulated dataset on this value." ${config.trail === true ? "checked" : ""}></td>
        <td><input type="radio" id="${attribute}InitialTabulate" name="initialTabulate" value="${attribute}" class="initial-sort-radio" title="Sort the tabulated dataset on this value initially." ${config.tabulate === "initial" ? "checked" : ""}></td>
      </tr>
    `;
		tbody.append(tr);
	}
}

// Function to update vis_parameters based on form inputs
function updateVisParameters() {
	$("#configurationTable .tabulate-checkbox").each(function() {
		const attribute = this.id;
		vis_parameters[attribute]["tabulate"] = this.checked;
	});

	$("#configurationTable .control-select").each(function() {
		const attribute = this.name.replace(/TemporalControl$/, "");
		vis_parameters[attribute]["temporal_control"] = this.value === "null" ? null : this.value;
	});

	$("#configurationTable .trail-checkbox").each(function() {
		const attribute = this.id.replace(/Trail$/, "");
		vis_parameters[attribute]["trail"] = this.checked;
	});

	$("#configurationTable .initial-sort-radio").each(function() {
		if (this.checked) {
			const attribute = this.value;
			vis_parameters[attribute]["tabulate"] = "initial";
		}
	});
	
	// Log the updated vis_parameters
	console.log('Updated vis_parameters:', vis_parameters);
}

// Function to toggle Control and Initial Sort controls based on Tabulate checkbox state
function toggleControls() {
	$(".tabulate-checkbox").each(function() {
		const controlSelect = $(this).closest("tr").find(".control-select");
		const trailCheckbox = $(this).closest("tr").find(".trail-checkbox");
		const initialSortRadio = $(this).closest("tr").find(".initial-sort-radio");

		controlSelect.prop("disabled", !this.checked);
		trailCheckbox.prop("disabled", !this.checked);
		initialSortRadio.prop("disabled", !this.checked);

		if (initialSortRadio.prop("disabled") && initialSortRadio.prop("checked")) {
			// Find the first enabled initial sort radio button
			const enabledInitialSortRadio = $(this).closest("tbody").find(".initial-sort-radio:not(:disabled)");
			if (enabledInitialSortRadio.length > 0) {
				enabledInitialSortRadio.prop("checked", true);
			}
		}
	});
}