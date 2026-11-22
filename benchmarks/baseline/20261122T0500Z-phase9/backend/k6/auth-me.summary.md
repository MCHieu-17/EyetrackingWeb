# k6 summary

scenario: me

- http_req_connecting: max=0.069, p(90)=0.000, p(95)=0.000, p(99)=0.036, avg=0.001, min=0.000, med=0.000
- http_req_duration{expected_response:true}: avg=7.757, min=1.907, med=8.364, max=9.858, p(90)=9.572, p(95)=9.706, p(99)=9.854
- http_req_receiving: avg=0.135, min=0.022, med=0.126, max=0.413, p(90)=0.207, p(95)=0.225, p(99)=0.334
- http_req_failed: rate=0.000
- vus: min=1.000, max=1.000
- http_req_blocked: avg=0.014, min=0.004, med=0.012, max=0.099, p(90)=0.014, p(95)=0.021, p(99)=0.066
- http_req_tls_handshaking: max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000
- http_req_duration: min=1.907, med=8.364, max=9.858, p(90)=9.572, p(95)=9.706, p(99)=9.854, avg=7.757
- http_req_sending: p(95)=0.054, p(99)=0.064, avg=0.041, min=0.014, med=0.041, max=0.066, p(90)=0.046
- http_req_waiting: avg=7.580, min=1.860, med=8.146, max=9.679, p(90)=9.381, p(95)=9.530, p(99)=9.640
- iterations: count=48.000, rate=4.790
