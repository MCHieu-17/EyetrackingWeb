# k6 summary

scenario: replay

- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- http_req_sending: avg=0.044, min=0.012, med=0.043, max=0.075, p(90)=0.059, p(95)=0.067, p(99)=0.074
- iterations: count=20.000, rate=4.096
- vus: min=1.000, max=1.000
- http_req_blocked: avg=0.017, min=0.003, med=0.011, max=0.110, p(90)=0.022, p(95)=0.027, p(99)=0.093
- http_req_connecting: med=0.000, max=0.078, p(90)=0.000, p(95)=0.004, p(99)=0.064, avg=0.004, min=0.000
- http_req_receiving: p(95)=0.245, p(99)=0.355, avg=0.133, min=0.065, med=0.109, max=0.383, p(90)=0.183
- http_req_duration{expected_response:true}: min=19.676, med=46.635, max=83.590, p(90)=52.974, p(95)=55.658, p(99)=78.003, avg=43.268
- http_req_failed: rate=0.000
- http_req_waiting: min=19.564, med=46.495, max=83.432, p(90)=52.847, p(95)=55.495, p(99)=77.845, avg=43.091
- http_req_duration: avg=43.268, min=19.676, med=46.635, max=83.590, p(90)=52.974, p(95)=55.658, p(99)=78.003
