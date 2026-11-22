# k6 summary

scenario: samples

- http_req_duration{expected_response:true}: med=16.877, max=58.554, p(90)=28.983, p(95)=31.445, p(99)=45.136, avg=17.821, min=5.574
- vus: min=5.000, max=5.000
- http_req_blocked: p(90)=0.014, p(95)=0.015, p(99)=0.087, avg=0.012, min=0.002, med=0.011, max=0.124
- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- http_req_waiting: avg=17.596, min=5.499, med=16.785, max=58.444, p(90)=28.437, p(95)=31.183, p(99)=45.005
- http_req_failed: rate=0.000
- http_req_duration: max=58.554, p(90)=28.983, p(95)=31.445, p(99)=45.136, avg=17.821, min=5.574, med=16.877
- http_req_sending: med=0.040, max=0.106, p(90)=0.050, p(95)=0.054, p(99)=0.087, avg=0.036, min=0.007
- iterations: count=231.000, rate=22.609
- http_req_connecting: p(99)=0.066, avg=0.002, min=0.000, med=0.000, max=0.088, p(90)=0.000, p(95)=0.000
- http_req_receiving: min=0.026, med=0.096, max=2.625, p(90)=0.353, p(95)=0.485, p(99)=1.983, avg=0.189
