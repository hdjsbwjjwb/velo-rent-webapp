let map;

// Функция инициализации карты
function initMap() {
    // Создаем карту с начальным центром и уровнем зума
    map = new google.maps.Map(document.getElementById("map"), {
        center: { lat: 54.9375, lng: 19.9750 }, // Координаты Балтийской косы
        zoom: 12,
    });

    // Точки маршрута: начальная и конечная
    const start = { lat: 54.9375, lng: 19.9750 }; // Балтийская коса
    const end = { lat: 55.7598, lng: 37.6216 }; // Примерная конечная точка (например, Москва)

    // Создаем объект DirectionsService для расчета маршрута
    const directionsService = new google.maps.DirectionsService();
    const directionsRenderer = new google.maps.DirectionsRenderer();
    directionsRenderer.setMap(map); // Устанавливаем отображение маршрута на карте

    // Запрос маршрута от start до end
    directionsService.route(
        {
            origin: start,
            destination: end,
            travelMode: google.maps.TravelMode.DRIVING, // Способ передвижения (можно изменить на WALKING, BICYCLING, TRANSIT)
        },
        (response, status) => {
            if (status === "OK") {
                directionsRenderer.setDirections(response); // Отображаем маршрут на карте
            } else {
                console.error("Ошибка маршрута: " + status); // В случае ошибки
            }
        }
    );
}
