# k6 summary

scenario: outline

- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_duration: min=1.912, med=8.005, max=11.388, p(90)=10.223, p(95)=10.835, p(99)=11.277, avg=7.480
- vus: min=1.000, max=1.000
- http_req_failed: rate=0.000
- http_req_blocked: p(95)=0.054, p(99)=0.089, avg=0.017, min=0.003, med=0.011, max=0.098, p(90)=0.022
- http_req_receiving: p(95)=0.270, p(99)=0.689, avg=0.165, min=0.034, med=0.138, max=0.794, p(90)=0.236
- http_req_connecting: p(90)=0.000, p(95)=0.003, p(99)=0.056, avg=0.003, min=0.000, med=0.000, max=0.069
- http_req_sending: avg=0.039, min=0.012, med=0.041, max=0.065, p(90)=0.051, p(95)=0.055, p(99)=0.063
- http_req_waiting: med=7.812, max=11.112, p(90)=9.638, p(95)=10.612, p(99)=11.012, avg=7.277, min=1.852
- iterations: count=20.000, rate=4.796
- http_req_duration{expected_response:true}: p(99)=11.277, avg=7.480, min=1.912, med=8.005, max=11.388, p(90)=10.223, p(95)=10.835
