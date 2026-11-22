# k6 summary

scenario: samples

- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- iterations: count=20.000, rate=4.678
- http_req_blocked: p(90)=0.015, p(95)=0.025, p(99)=0.100, avg=0.017, min=0.009, med=0.011, max=0.119
- http_req_receiving: avg=0.102, min=0.030, med=0.102, max=0.281, p(90)=0.157, p(95)=0.184, p(99)=0.262
- http_req_failed: rate=0.000
- http_req_duration: p(95)=17.699, p(99)=17.906, avg=12.668, min=4.219, med=14.315, max=17.958, p(90)=17.473
- http_req_waiting: min=4.132, med=14.150, max=17.796, p(90)=17.316, p(95)=17.526, p(99)=17.742, avg=12.522
- vus: min=1.000, max=1.000
- http_req_duration{expected_response:true}: med=14.315, max=17.958, p(90)=17.473, p(95)=17.699, p(99)=17.906, avg=12.668, min=4.219
- http_req_connecting: med=0.000, max=0.084, p(90)=0.000, p(95)=0.004, p(99)=0.068, avg=0.004, min=0.000
- http_req_sending: med=0.043, max=0.057, p(90)=0.050, p(95)=0.051, p(99)=0.056, avg=0.044, min=0.034
