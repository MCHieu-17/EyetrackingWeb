# k6 summary

scenario: me

- vus: min=1.000, max=1.000
- http_req_tls_handshaking: max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000
- iterations: count=48.000, rate=4.780
- http_req_duration{expected_response:true}: p(90)=9.801, p(95)=9.930, p(99)=10.038, avg=8.042, min=1.856, med=9.056, max=10.090
- http_req_duration: avg=8.042, min=1.856, med=9.056, max=10.090, p(90)=9.801, p(95)=9.930, p(99)=10.038
- http_req_failed: rate=0.000
- http_req_sending: avg=0.040, min=0.012, med=0.041, max=0.071, p(90)=0.049, p(95)=0.052, p(99)=0.065
- http_req_connecting: p(95)=0.000, p(99)=0.044, avg=0.002, min=0.000, med=0.000, max=0.084, p(90)=0.000
- http_req_blocked: avg=0.013, min=0.004, med=0.011, max=0.115, p(90)=0.013, p(95)=0.013, p(99)=0.068
- http_req_waiting: avg=7.893, min=1.812, med=8.880, max=9.920, p(90)=9.620, p(95)=9.774, p(99)=9.878
- http_req_receiving: avg=0.109, min=0.021, med=0.117, max=0.181, p(90)=0.153, p(95)=0.171, p(99)=0.178
