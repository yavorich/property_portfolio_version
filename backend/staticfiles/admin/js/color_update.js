document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".color-input").forEach(function (input) {
        input.addEventListener("input", function () {
            const id = this.dataset.id;
            const color = this.value;
            const field = this.dataset.field;
            const checkmark = this.closest("div").querySelector(".save-check");

            const url = new URL("update-color/", window.location.href);

            fetch(url, {
                method: "POST",
                headers: {
                    "X-CSRFToken": getCookie("csrftoken"),
                    "Accept": "application/json",
                },
                body: new URLSearchParams({ id: id, color: color, field: field })
            })
            .then(async res => {
                if (!res.ok) {
                    const text = await res.text();
                    console.error("Ошибка сервера:", text);
                    throw new Error("Server returned non-JSON response");
                }
                return res.json();
            })
            .then(data => {
                if (data.success) {
                    checkmark.style.display = "inline";
                    setTimeout(() => { checkmark.style.display = "none"; }, 1000);
                } else {
                    console.error("Ошибка сохранения:", data.error);
                }
            })
            .catch(err => console.error("Fetch error:", err));
        });
    });
});

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
        const cookies = document.cookie.split(";").map(c => c.trim());
        for (let cookie of cookies) {
            if (cookie.startsWith(name + "=")) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}