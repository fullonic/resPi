### ResPi system main repository (2020)

This project is fruit of a collaboration with an ecology research group of the _Institut d’Ecologia Aquàtica_, Universitat de Girona (UdG).
The developed system controls an aquarium water pump and help during the data processing for the study of the glass eels metabolism.
Originally built as a single application, due to the necessary increase of computational power to process and analyze the data collected, it ended up being two separated applications.

- [ResPi Controller](https://github.com/fullonic/respi/tree/resPi_controller): A water pump automation system based on the raspberry Pi Zero W and controlled remotely
- [ResPi Converter](https://github.com/fullonic/respi/tree/resPi_converter): An application that receives a data file from the  oxygen and temperature probe to analyze, clean, calculate and plot the information.

It was developed using _`python 3.8`_ and each application have it's own dependencies. While is a fully operational system that meets the needs of the research team, there is some room for improvements. It can change overtime if new features are required.
