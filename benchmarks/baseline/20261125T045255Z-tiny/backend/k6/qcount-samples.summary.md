# k6 summary

scenario: samples

- http_req_duration: p(95)=17.951, p(99)=18.041, avg=12.846, min=3.584, med=15.769, max=18.064, p(90)=17.933
- http_req_sending: avg=0.040, min=0.011, med=0.044, max=0.062, p(90)=0.054, p(95)=0.059, p(99)=0.062
- http_req_waiting: min=3.508, med=15.558, max=17.852, p(90)=17.735, p(95)=17.792, p(99)=17.840, avg=12.694
- http_req_failed: rate=0.000
- vus: min=1.000, max=1.000
- http_req_blocked: min=0.003, med=0.011, max=0.115, p(90)=0.018, p(95)=0.026, p(99)=0.097, avg=0.016
- http_req_connecting: p(99)=0.067, avg=0.004, min=0.000, med=0.000, max=0.083, p(90)=0.000, p(95)=0.004
- iterations: count=20.000, rate=4.677
- http_req_duration{expected_response:true}: min=3.584, med=15.769, max=18.064, p(90)=17.933, p(95)=17.951, p(99)=18.041, avg=12.846
- http_req_receiving: max=0.185, p(90)=0.172, p(95)=0.181, p(99)=0.184, avg=0.112, min=0.029, med=0.114
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
