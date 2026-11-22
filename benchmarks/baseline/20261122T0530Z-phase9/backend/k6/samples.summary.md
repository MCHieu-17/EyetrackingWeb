# k6 summary

scenario: samples

- http_req_sending: min=0.006, med=0.041, max=0.163, p(90)=0.050, p(95)=0.058, p(99)=0.079, avg=0.038
- http_req_duration: avg=18.041, min=5.456, med=17.557, max=57.851, p(90)=26.071, p(95)=27.378, p(99)=46.915
- http_req_duration{expected_response:true}: avg=18.041, min=5.456, med=17.557, max=57.851, p(90)=26.071, p(95)=27.378, p(99)=46.915
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_connecting: max=0.099, p(90)=0.000, p(95)=0.000, p(99)=0.075, avg=0.002, min=0.000, med=0.000
- vus: min=5.000, max=5.000
- http_req_failed: rate=0.000
- http_req_waiting: avg=17.911, min=5.367, med=17.401, max=57.767, p(90)=25.950, p(95)=27.266, p(99)=46.851
- http_req_receiving: max=0.404, p(90)=0.149, p(95)=0.192, p(99)=0.327, avg=0.092, min=0.027, med=0.078
- http_req_blocked: min=0.002, med=0.011, max=0.127, p(90)=0.014, p(95)=0.016, p(99)=0.099, avg=0.012
- iterations: count=232.000, rate=22.732
