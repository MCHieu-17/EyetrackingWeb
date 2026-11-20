# k6 summary

scenario: enrollments

- http_req_duration{expected_response:true}: avg=8.253, min=1.255, med=8.196, max=13.524, p(90)=11.609, p(95)=11.862, p(99)=12.629
- http_req_tls_handshaking: p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000
- http_req_receiving: p(90)=0.750, p(95)=0.858, p(99)=1.116, avg=0.320, min=0.025, med=0.229, max=1.634
- http_req_blocked: p(99)=0.122, avg=0.013, min=0.002, med=0.011, max=0.129, p(90)=0.014, p(95)=0.019
- http_req_sending: p(99)=0.076, avg=0.038, min=0.005, med=0.039, max=0.133, p(90)=0.048, p(95)=0.054
- http_req_connecting: p(95)=0.000, p(99)=0.093, avg=0.002, min=0.000, med=0.000, max=0.096, p(90)=0.000
- http_req_duration: p(95)=11.862, p(99)=12.629, avg=8.253, min=1.255, med=8.196, max=13.524, p(90)=11.609
- iterations: count=242.000, rate=23.766
- vus: min=5.000, max=5.000
- http_req_failed: rate=0.000
- http_req_waiting: p(95)=11.367, p(99)=12.034, avg=7.894, min=1.196, med=7.836, max=13.261, p(90)=10.985
