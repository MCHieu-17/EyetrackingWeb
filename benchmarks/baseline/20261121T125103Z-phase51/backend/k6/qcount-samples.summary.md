# k6 summary

scenario: samples

- http_req_connecting: avg=0.003, min=0.000, med=0.000, max=0.066, p(90)=0.000, p(95)=0.003, p(99)=0.054
- http_req_sending: p(99)=0.057, avg=0.040, min=0.012, med=0.041, max=0.058, p(90)=0.049, p(95)=0.050
- iterations: count=20.000, rate=4.580
- http_req_failed: rate=0.000
- vus: max=1.000, min=1.000
- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- http_req_waiting: med=17.456, max=26.079, p(90)=24.744, p(95)=24.891, p(99)=25.841, avg=17.010, min=6.171
- http_req_blocked: avg=0.016, min=0.004, med=0.011, max=0.093, p(90)=0.021, p(95)=0.025, p(99)=0.079
- http_req_receiving: avg=0.164, min=0.059, med=0.131, max=0.906, p(90)=0.178, p(95)=0.233, p(99)=0.771
- http_req_duration{expected_response:true}: p(99)=26.020, avg=17.215, min=6.306, med=17.882, max=26.259, p(90)=24.975, p(95)=25.065
- http_req_duration: avg=17.215, min=6.306, med=17.882, max=26.259, p(90)=24.975, p(95)=25.065, p(99)=26.020
