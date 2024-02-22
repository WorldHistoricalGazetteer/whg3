import '../css/vis_parameters.css';

class VisualisationControl { 
    constructor() {
		this.configurationTable = $("#configurationTable");
		if (this.configurationTable.length === 0) return null;
        const visParametersData = JSON.parse(this.configurationTable.find('#vis_parameters_data').html());
        this.vis_parameters = visParametersData || {}; // If JSON data is not available, initialize an empty object
        this.initialize();
        return this.configurationTable;
    }

    initialize() {

        if (Object.keys(this.vis_parameters).length === 0) {
            this.vis_parameters = {
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
            console.log('vis_parameters was undefined or empty, so set to default values.');
        }
        console.log('vis_parameters:', this.vis_parameters);

	    const thead = $('<thead><tr><th colspan="2" style="text-align: right;">Include</th><th>Temporal</th><th>Trail</th><th>Sort</th></tr></thead>');
		const tbody = $('<tbody></tbody>');
	    this.configurationTable.empty().append(thead).append(tbody);

        this.generateConfigurationRows();

        // Add event listeners to all input elements to update vis_parameters and toggle controls
        $("#configurationTable").on("change", ".tabulate-checkbox", this.toggleControls.bind(this));
        $("#configurationTable").on("change", "input, select", this.updateVisParameters.bind(this));

        // Call toggleControls initially to set initial state
        this.toggleControls();
        
		$('#collection_form').on('submit', () => { // Add/update hidden Form value before submission		    
		    let visParametersInput = $('#visParameters');
		    if (visParametersInput.length === 0) {
		        visParametersInput = $('<input type="hidden" id="visParameters" name="vis_parameters">');
		        $('#collection_form').append(visParametersInput);
		    }
		    visParametersInput.val(JSON.stringify(this.vis_parameters));
		});        
        
    }

    generateConfigurationRows() {
        const labelDictionary = {
            seq: "Sequence",
            min: "Start-date",
            max: "End-date"
        };

        const temporalControlOptions = {
            player: "Sequencer",
            filter: "Date Slider",
            null: "None"
        };

        const tbody = $("#configurationTable tbody");
        tbody.empty(); // Clear previous content
        
        // Get and sort the attribute keys present in vis_parameters
		const existingAttributes = Object.keys(this.vis_parameters)
		    .filter(attribute => attribute in labelDictionary)
		    .sort((a, b) => {
		        return Object.keys(labelDictionary).indexOf(a) - Object.keys(labelDictionary).indexOf(b);
		    });
		    
		existingAttributes.forEach(attribute => {
		    const config = this.vis_parameters[attribute];
            const label = labelDictionary[attribute];
            const optionHTML = Object.entries(temporalControlOptions)
			    .map(([value, text]) => {
			        const selected = (value === config.temporal_control) || (config.temporal_control === null && value === "null") ? "selected" : "";
        			return `<option value="${value}" ${selected}>${text}</option>`;
			    })
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
        });
    }

    updateVisParameters() {
		
		var vis_parameters = this.vis_parameters;
		
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
        console.log('Updated vis_parameters:', this.vis_parameters);
    }

    toggleControls() {
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
                else {
					initialSortRadio.prop("checked", false);
				}
            }
        });
        
        const enabledRadios = $(".initial-sort-radio:not(:disabled)");
        if (enabledRadios.length === 1) {
	        enabledRadios.prop("checked", true);
	    }
        
    }
}

export default VisualisationControl;
