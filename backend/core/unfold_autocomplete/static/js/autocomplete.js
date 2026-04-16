document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("select[data-options-map]").forEach(select => {
        const dependsOnField = select.dataset.dependsField;
        const optionsMap = JSON.parse(select.dataset.optionsMap || "{}");
        const originalOptions = Array.from(select.options);

        document.getElementsByName(dependsOnField).forEach(
            dependsOnElem => {
                function updateOptions() {
                    const selectedValue = dependsOnElem.value;

                    if (!(optionsMap[select.value] || []).includes(selectedValue) ) {
                        select.value = ""
                    }

                    for (let option of select.options) {
                        if (option.value !== "") {
                            option.hidden = !(optionsMap[option.value] || []).includes(selectedValue);
                        }
                    }
                }

                dependsOnElem.addEventListener('change', updateOptions);
                updateOptions();
            }
        );
    });
});
