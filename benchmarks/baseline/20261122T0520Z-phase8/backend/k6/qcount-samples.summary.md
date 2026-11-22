# k6 summary

scenario: samples

- http_req_connecting: max=0.573, p(90)=0.000, p(95)=0.029, p(99)=0.464, avg=0.029, min=0.000, med=0.000
- http_req_sending: p(90)=0.053, p(95)=0.086, p(99)=0.549, avg=0.072, min=0.011, med=0.043, max=0.664
- http_req_receiving: p(99)=0.330, avg=0.138, min=0.071, med=0.126, max=0.362, p(90)=0.193, p(95)=0.203
- http_req_failed: rate=0.000
- http_req_waiting: avg=18.261, min=5.647, med=21.451, max=24.151, p(90)=23.208, p(95)=23.524, p(99)=24.026
- http_req_duration{expected_response:true}: avg=18.471, min=5.754, med=21.604, max=24.385, p(90)=23.391, p(95)=23.672, p(99)=24.242
- http_req_tls_handshaking: p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000
- http_req_duration: avg=18.471, min=5.754, med=21.604, max=24.385, p(90)=23.391, p(95)=23.672, p(99)=24.242
- iterations: count=20.000, rate=4.556
- http_req_blocked: med=0.011, max=0.758, p(90)=0.013, p(95)=0.051, p(99)=0.617, avg=0.048, min=0.003
- vus: max=1.000, min=1.000
