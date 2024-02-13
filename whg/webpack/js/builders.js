// builders.js is for the "build" pages
// place_collection_build.html, ds_summary.html, and ds_collection_build.html


// Default vis_parameters object: update with any value previously configured for the dataset/collection
var vis_parameters = {
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

// Function to generate the configuration table rows dynamically based on vis_parameters
function generateConfigurationRows() {
  const tbody = document.querySelector("#configurationTable tbody");
  tbody.innerHTML = ""; // Clear previous content

  for (const attribute in vis_parameters) {
    const config = vis_parameters[attribute];
    const label = labelDictionary[attribute];

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td style="text-align: right;">${label}:</td>
      <td><input type="checkbox" id="${attribute}" name="${attribute}Tabulate" class="tabulate-checkbox" title="Should this value be included in the tabulation of the dataset?" ${
      config.tabulate !== false ? "checked" : ""
    }></td>
      <td>
        <select name="${attribute}TemporalControl" class="control-select" title="Choose (or remove) a temporal control to be used when sorting the tabulated dataset on this value.">
          ${Object.entries(temporalControlOptions)
            .map(
              ([value, text]) =>
                `<option value="${value}" ${
                  config.temporal_control === value ? "selected" : ""
                }>${text}</option>`
            )
            .join("")}
        </select>
      </td>
      <td><input type="checkbox" id="${attribute}Trail" name="${attribute}Trail" class="trail-checkbox" title="Draw map-trails between consecutive features when sorting the tabulated dataset on this value." ${
      config.trail === true ? "checked" : ""
    }></td>
      <td><input type="radio" id="${attribute}InitialTabulate" name="initialTabulate" value="${attribute}" class="initial-sort-radio" title="Sort the tabulated dataset on this value initially." ${
      config.tabulate === "initial" ? "checked" : ""
    }></td>
    `;
    tbody.appendChild(tr);
  }

  // Add event listeners to all input elements to update vis_parameters
  const inputs = document.querySelectorAll(
    "#configurationTable input, #configurationTable select"
  );
  inputs.forEach(function (input) {
    input.addEventListener("change", updateVisParameters);
  });
}

// Function to update vis_parameters based on form inputs
function updateVisParameters() {
  // Update vis_parameters based on Tabulate checkboxes
  const tabulateCheckboxes = document.querySelectorAll(".tabulate-checkbox");
  tabulateCheckboxes.forEach(function (checkbox) {
    const attribute = checkbox.id;
    vis_parameters[attribute]["tabulate"] = checkbox.checked;
  });

  // Update vis_parameters based on Control select elements
  const controlSelects = document.querySelectorAll(".control-select");
  controlSelects.forEach(function (select) {
    const attribute = select.name.replace(/TemporalControl$/, "");
    vis_parameters[attribute]["temporal_control"] =
      select.value === "null" ? null : select.value;
  });

  // Update vis_parameters based on Trail checkboxes
  const trailCheckboxes = document.querySelectorAll(".trail-checkbox");
  trailCheckboxes.forEach(function (checkbox) {
    const attribute = checkbox.id.replace(/Trail$/, "");
    vis_parameters[attribute]["trail"] = checkbox.checked;
  });

  // Update vis_parameters based on Initial Sort radio buttons
  const initialSortRadios = document.querySelectorAll(".initial-sort-radio");
  initialSortRadios.forEach(function (radio) {
    if (radio.checked) {
      const attribute = radio.value;
      vis_parameters[attribute]["tabulate"] = "initial";
    }
  });

  // Log the updated vis_parameters
  console.log(vis_parameters);
}

// Call the function to generate configuration table rows
generateConfigurationRows();

// Function to toggle Control and Initial Sort controls based on Tabulate checkbox state
function toggleControls() {
  const tabulateCheckboxes = document.querySelectorAll(".tabulate-checkbox");
  tabulateCheckboxes.forEach(function (checkbox) {
    const controlSelect = checkbox.parentNode.nextElementSibling.querySelector(
      ".control-select"
    );
    const trailCheckbox = checkbox.parentNode.nextElementSibling.nextElementSibling.querySelector(
      ".trail-checkbox"
    );
    const initialSortRadio = checkbox.parentNode.nextElementSibling.nextElementSibling.nextElementSibling.querySelector(
      ".initial-sort-radio"
    );

    controlSelect.disabled = !checkbox.checked;
    trailCheckbox.disabled = !checkbox.checked;
    initialSortRadio.disabled = !checkbox.checked;

    if (initialSortRadio.disabled && initialSortRadio.checked) {
      // Find the first enabled initial sort radio button
      const enabledInitialSortRadio = checkbox
        .closest("tbody")
        .querySelector(".initial-sort-radio:not(:disabled)");
      if (enabledInitialSortRadio) {
        enabledInitialSortRadio.checked = true;
      }
    }
  });
}

// Add event listeners to Tabulate checkboxes to call toggleControls function
const tabulateCheckboxes = document.querySelectorAll(".tabulate-checkbox");
tabulateCheckboxes.forEach(function (checkbox) {
  checkbox.addEventListener("change", toggleControls);
});

// Call toggleControls initially to set initial state
toggleControls();

